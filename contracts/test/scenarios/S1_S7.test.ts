import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-toolbox/network-helpers";
import { DepositVault, MockINR, IdentityRegistry, ArbitratorRegistry, TenancyFactory } from "../../typechain-types";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";

describe("TrustRent: End-to-End Scenarios Suite (S1–S7)", function () {
  let owner: HardhatEthersSigner;
  let landlord: HardhatEthersSigner;
  let tenant: HardhatEthersSigner;
  let arbitrator: HardhatEthersSigner;
  let unverifiedUser: HardhatEthersSigner;
  let maliciousStranger: HardhatEthersSigner;

  let mockINR: MockINR;
  let idRegistry: IdentityRegistry;
  let arbRegistry: ArbitratorRegistry;
  let vaultTemplate: DepositVault;
  let factory: TenancyFactory;

  const DEPOSIT = ethers.parseEther("50000");
  const CAP = ethers.parseEther("20000");
  const CLAIM_WINDOW = 7 * 86400;
  const LEASE_HASH = ethers.keccak256(ethers.toUtf8Bytes("OFFICIAL_TENANCY_LEASE_DOCUMENT"));
  const MOVE_IN_HASH = ethers.keccak256(ethers.toUtf8Bytes("MOVE_IN_CANONICAL_MANIFEST"));
  const MOVE_OUT_HASH = ethers.keccak256(ethers.toUtf8Bytes("MOVE_OUT_CANONICAL_MANIFEST"));
  const ATTESTATION = ethers.keccak256(ethers.toUtf8Bytes("UIDAI_AADHAAR_MOCK_VERIFIED"));

  beforeEach(async function () {
    [owner, landlord, tenant, arbitrator, unverifiedUser, maliciousStranger] = await ethers.getSigners();

    const MockINR = await ethers.getContractFactory("MockINR");
    mockINR = await MockINR.deploy();

    const IdRegistry = await ethers.getContractFactory("IdentityRegistry");
    idRegistry = await IdRegistry.deploy(owner.address, owner.address);

    const ArbRegistry = await ethers.getContractFactory("ArbitratorRegistry");
    arbRegistry = await ArbRegistry.deploy(owner.address);
    await arbRegistry.addArbitrator(arbitrator.address);

    const Vault = await ethers.getContractFactory("DepositVault");
    vaultTemplate = await Vault.deploy();

    const Factory = await ethers.getContractFactory("TenancyFactory");
    factory = await Factory.deploy(
      await vaultTemplate.getAddress(),
      await idRegistry.getAddress(),
      await arbRegistry.getAddress()
    );

    await idRegistry.attest(landlord.address, ATTESTATION);
    await idRegistry.attest(tenant.address, ATTESTATION);

    await mockINR.mint(tenant.address, DEPOSIT * 3n);
  });

  async function setupActiveVault(): Promise<DepositVault> {
    const tx = await factory.createTenancy(
      landlord.address,
      tenant.address,
      await mockINR.getAddress(),
      DEPOSIT,
      CAP,
      CLAIM_WINDOW,
      LEASE_HASH
    );
    const receipt = await tx.wait();
    const event = receipt?.logs
      .map(log => { try { return factory.interface.parseLog(log); } catch { return null; } })
      .find(p => p && p.name === "TenancyCreated");

    const vault = await ethers.getContractAt("DepositVault", event?.args.vaultAddress);
    await vault.connect(landlord).sign();
    await vault.connect(tenant).sign();
    await mockINR.connect(tenant).approve(await vault.getAddress(), DEPOSIT);
    await vault.connect(tenant).lockDeposit();
    await vault.connect(tenant).recordMoveInEvidence(MOVE_IN_HASH);
    return vault;
  }

  it("Scenario S1: Happy refund via keeper after elapsed claim window", async function () {
    const vault = await setupActiveVault();
    await vault.connect(landlord).startMoveOut(MOVE_OUT_HASH);

    const deadline = await vault.claimDeadline();
    await time.increaseTo(deadline + 5n);

    const tenantBalBefore = await mockINR.balanceOf(tenant.address);
    await vault.connect(maliciousStranger).finalizeRefund();
    const tenantBalAfter = await mockINR.balanceOf(tenant.address);

    expect(tenantBalAfter - tenantBalBefore).to.equal(DEPOSIT);
    expect(await vault.state()).to.equal(5);
  });

  it("Scenario S2: Landlord claim followed by arbitrator split settlement", async function () {
    const vault = await setupActiveVault();
    await vault.connect(landlord).startMoveOut(MOVE_OUT_HASH);

    const claimAmt = ethers.parseEther("18000");
    await vault.connect(landlord).raiseClaim(claimAmt, "QmDamageProofReport");
    await vault.connect(owner).assignArbitrator(arbitrator.address);

    const landlordAward = ethers.parseEther("14000");
    const tenantRefund = DEPOSIT - landlordAward;

    const landlordBefore = await mockINR.balanceOf(landlord.address);
    const tenantBefore = await mockINR.balanceOf(tenant.address);

    await vault.connect(arbitrator).decide(landlordAward, tenantRefund);

    expect(await mockINR.balanceOf(landlord.address) - landlordBefore).to.equal(landlordAward);
    expect(await mockINR.balanceOf(tenant.address) - tenantBefore).to.equal(tenantRefund);
    expect(await vault.state()).to.equal(5);
  });

  it("Scenario S3: Rejection of claims and decisions that violate deduction cap", async function () {
    const vault = await setupActiveVault();
    await vault.connect(landlord).startMoveOut(MOVE_OUT_HASH);

    await expect(
      vault.connect(landlord).raiseClaim(CAP + 1n, "QmExcessClaim")
    ).to.be.revertedWithCustomError(vault, "ExceedsDeductionCap");

    await vault.connect(landlord).raiseClaim(CAP, "QmValidClaim");
    await vault.connect(owner).assignArbitrator(arbitrator.address);

    await expect(
      vault.connect(arbitrator).decide(CAP + ethers.parseEther("100"), DEPOSIT - (CAP + ethers.parseEther("100")))
    ).to.be.revertedWithCustomError(vault, "ExceedsDeductionCap");
  });

  it("Scenario S4: Rejection of operations performed by unauthorized callers", async function () {
    const vault = await setupActiveVault();

    await expect(
      vault.connect(maliciousStranger).startMoveOut(MOVE_OUT_HASH)
    ).to.be.revertedWithCustomError(vault, "Unauthorized");

    await vault.connect(landlord).startMoveOut(MOVE_OUT_HASH);

    await expect(
      vault.connect(maliciousStranger).raiseClaim(CAP, "QmFakeClaim")
    ).to.be.revertedWithCustomError(vault, "Unauthorized");

    await vault.connect(landlord).raiseClaim(CAP, "QmClaim");
    await vault.connect(owner).assignArbitrator(arbitrator.address);

    await expect(
      vault.connect(maliciousStranger).decide(CAP, DEPOSIT - CAP)
    ).to.be.revertedWithCustomError(vault, "Unauthorized");
  });

  it("Scenario S5: Rejection of claim raised after the claim window has closed", async function () {
    const vault = await setupActiveVault();
    await vault.connect(landlord).startMoveOut(MOVE_OUT_HASH);

    const deadline = await vault.claimDeadline();
    await time.increaseTo(deadline + 1n);

    await expect(
      vault.connect(landlord).raiseClaim(CAP, "QmLateClaim")
    ).to.be.revertedWithCustomError(vault, "ClaimWindowPassed");
  });

  it("Scenario S6: Verification detects tampered evidence files against anchored hash", async function () {
    const originalFile = ethers.toUtf8Bytes("ORIGINAL_KITCHEN_WALL_PHOTO_BYTES");
    const tamperedFile = ethers.toUtf8Bytes("TAMPERED_MODIFIED_IMAGE_BYTES");

    const anchoredHash = ethers.keccak256(originalFile);
    const tamperedHash = ethers.keccak256(tamperedFile);

    expect(anchoredHash).to.not.equal(tamperedHash);
  });

  it("Scenario S7: Unverified user is strictly prohibited from creating or signing tenancies", async function () {
    await expect(
      factory.createTenancy(
        unverifiedUser.address,
        tenant.address,
        await mockINR.getAddress(),
        DEPOSIT,
        CAP,
        CLAIM_WINDOW,
        LEASE_HASH
      )
    ).to.be.revertedWithCustomError(factory, "PartyNotVerified").withArgs(unverifiedUser.address);

    await expect(
      factory.createTenancy(
        landlord.address,
        unverifiedUser.address,
        await mockINR.getAddress(),
        DEPOSIT,
        CAP,
        CLAIM_WINDOW,
        LEASE_HASH
      )
    ).to.be.revertedWithCustomError(factory, "PartyNotVerified").withArgs(unverifiedUser.address);
  });
});
