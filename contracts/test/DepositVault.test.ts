import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-toolbox/network-helpers";
import { DepositVault, MockINR, IdentityRegistry, ArbitratorRegistry, TenancyFactory } from "../typechain-types";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";

describe("TrustRent: Smart Contracts Comprehensive Test Suite", function () {
  let owner: HardhatEthersSigner;
  let landlord: HardhatEthersSigner;
  let tenant: HardhatEthersSigner;
  let arbitrator: HardhatEthersSigner;
  let stranger: HardhatEthersSigner;

  let mockINR: MockINR;
  let idRegistry: IdentityRegistry;
  let arbRegistry: ArbitratorRegistry;
  let vaultImplementation: DepositVault;
  let factory: TenancyFactory;

  const DEPOSIT_AMOUNT = ethers.parseEther("50000");
  const DEDUCTION_CAP = ethers.parseEther("20000");
  const CLAIM_WINDOW = 7 * 24 * 60 * 60;
  const MOCK_LEASE_HASH = ethers.keccak256(ethers.toUtf8Bytes("LEGAL_LEASE_DOCUMENT_V1"));
  const MOCK_MOVE_IN_HASH = ethers.keccak256(ethers.toUtf8Bytes("MOVE_IN_EVIDENCE_MANIFEST"));
  const MOCK_MOVE_OUT_HASH = ethers.keccak256(ethers.toUtf8Bytes("MOVE_OUT_EVIDENCE_MANIFEST"));
  const ATTESTATION_HASH = ethers.keccak256(ethers.toUtf8Bytes("GOV_ID_VERIFIED"));

  beforeEach(async function () {
    [owner, landlord, tenant, arbitrator, stranger] = await ethers.getSigners();

    const MockINRFactory = await ethers.getContractFactory("MockINR");
    mockINR = await MockINRFactory.deploy();

    const IdRegistryFactory = await ethers.getContractFactory("IdentityRegistry");
    idRegistry = await IdRegistryFactory.deploy(owner.address, owner.address);

    const ArbRegistryFactory = await ethers.getContractFactory("ArbitratorRegistry");
    arbRegistry = await ArbRegistryFactory.deploy(owner.address);
    await arbRegistry.addArbitrator(arbitrator.address);

    const VaultFactory = await ethers.getContractFactory("DepositVault");
    vaultImplementation = await VaultFactory.deploy();

    const FactoryFactory = await ethers.getContractFactory("TenancyFactory");
    factory = await FactoryFactory.deploy(
      await vaultImplementation.getAddress(),
      await idRegistry.getAddress(),
      await arbRegistry.getAddress()
    );

    await idRegistry.attest(landlord.address, ATTESTATION_HASH);
    await idRegistry.attest(tenant.address, ATTESTATION_HASH);

    await mockINR.mint(tenant.address, DEPOSIT_AMOUNT * 5n);
  });

  async function createValidVault(): Promise<DepositVault> {
    const tx = await factory.createTenancy(
      landlord.address,
      tenant.address,
      await mockINR.getAddress(),
      DEPOSIT_AMOUNT,
      DEDUCTION_CAP,
      CLAIM_WINDOW,
      MOCK_LEASE_HASH
    );
    const receipt = await tx.wait();
    expect(receipt).to.not.be.null;

    const event = receipt?.logs
      .map(log => {
        try { return factory.interface.parseLog(log); } catch { return null; }
      })
      .find(parsed => parsed && parsed.name === "TenancyCreated");

    const vaultAddr = event?.args.vaultAddress;
    return await ethers.getContractAt("DepositVault", vaultAddr);
  }

  describe("1. TenancyFactory & Pre-Validation Guards", function () {
    it("Should reject vault creation if landlord is not verified", async function () {
      await expect(
        factory.createTenancy(
          stranger.address,
          tenant.address,
          await mockINR.getAddress(),
          DEPOSIT_AMOUNT,
          DEDUCTION_CAP,
          CLAIM_WINDOW,
          MOCK_LEASE_HASH
        )
      ).to.be.revertedWithCustomError(factory, "PartyNotVerified").withArgs(stranger.address);
    });

    it("Should reject vault creation if tenant is not verified", async function () {
      await expect(
        factory.createTenancy(
          landlord.address,
          stranger.address,
          await mockINR.getAddress(),
          DEPOSIT_AMOUNT,
          DEDUCTION_CAP,
          CLAIM_WINDOW,
          MOCK_LEASE_HASH
        )
      ).to.be.revertedWithCustomError(factory, "PartyNotVerified").withArgs(stranger.address);
    });

    it("Should reject self-tenancy (landlord == tenant)", async function () {
      await expect(
        factory.createTenancy(
          landlord.address,
          landlord.address,
          await mockINR.getAddress(),
          DEPOSIT_AMOUNT,
          DEDUCTION_CAP,
          CLAIM_WINDOW,
          MOCK_LEASE_HASH
        )
      ).to.be.revertedWithCustomError(factory, "SelfTenancyNotAllowed");
    });

    it("Should reject deduction cap exceeding deposit amount", async function () {
      await expect(
        factory.createTenancy(
          landlord.address,
          tenant.address,
          await mockINR.getAddress(),
          DEPOSIT_AMOUNT,
          DEPOSIT_AMOUNT + 1n,
          CLAIM_WINDOW,
          MOCK_LEASE_HASH
        )
      ).to.be.revertedWithCustomError(factory, "InvalidParameters");
    });

    it("Should reject claim window outside 3 to 30 days (TBD-1)", async function () {
      const TWO_DAYS = 2 * 24 * 60 * 60;
      const THIRTY_ONE_DAYS = 31 * 24 * 60 * 60;

      await expect(
        factory.createTenancy(
          landlord.address,
          tenant.address,
          await mockINR.getAddress(),
          DEPOSIT_AMOUNT,
          DEDUCTION_CAP,
          TWO_DAYS,
          MOCK_LEASE_HASH
        )
      ).to.be.revertedWithCustomError(factory, "InvalidParameters");

      await expect(
        factory.createTenancy(
          landlord.address,
          tenant.address,
          await mockINR.getAddress(),
          DEPOSIT_AMOUNT,
          DEDUCTION_CAP,
          THIRTY_ONE_DAYS,
          MOCK_LEASE_HASH
        )
      ).to.be.revertedWithCustomError(factory, "InvalidParameters");
    });

    it("Should deploy clone, emit TenancyCreated, and update user records", async function () {
      const vault = await createValidVault();
      expect(await vault.landlord()).to.equal(landlord.address);
      expect(await vault.tenant()).to.equal(tenant.address);
      expect(await vault.depositAmount()).to.equal(DEPOSIT_AMOUNT);
      expect(await vault.deductionCap()).to.equal(DEDUCTION_CAP);
      expect(await vault.state()).to.equal(0);

      const landlordTenancies = await factory.getTenanciesForUser(landlord.address);
      expect(landlordTenancies).to.include(await vault.getAddress());

      const tenantTenancies = await factory.getTenanciesForUser(tenant.address);
      expect(tenantTenancies).to.include(await vault.getAddress());
      expect(await factory.totalTenancies()).to.be.greaterThan(0);
    });

    it("Should revert factory deployment on zero addresses", async function () {
      const FactoryFactory = await ethers.getContractFactory("TenancyFactory");
      await expect(
        FactoryFactory.deploy(ethers.ZeroAddress, await idRegistry.getAddress(), await arbRegistry.getAddress())
      ).to.be.revertedWithCustomError(factory, "InvalidParameters");
    });

    it("Should support full IdentityRegistry attest, verify, revoke, and getAttestation lifecycle", async function () {
      const tempUser = stranger.address;
      expect(await idRegistry.isVerified(tempUser)).to.be.false;

      await idRegistry.connect(owner).attest(tempUser, ATTESTATION_HASH);
      expect(await idRegistry.isVerified(tempUser)).to.be.true;

      const [hash, ts, active] = await idRegistry.getAttestation(tempUser);
      expect(hash).to.equal(ATTESTATION_HASH);
      expect(active).to.be.true;
      expect(ts).to.be.greaterThan(0);

      await idRegistry.connect(owner).revoke(tempUser);
      expect(await idRegistry.isVerified(tempUser)).to.be.false;

      await expect(idRegistry.connect(owner).revoke(tempUser)).to.be.revertedWithCustomError(
        idRegistry,
        "NotVerified"
      );
    });

    it("Should support ArbitratorRegistry add and remove lifecycle", async function () {
      const newArb = stranger.address;
      expect(await arbRegistry.isApproved(newArb)).to.be.false;

      await arbRegistry.connect(owner).addArbitrator(newArb);
      expect(await arbRegistry.isApproved(newArb)).to.be.true;

      await arbRegistry.connect(owner).removeArbitrator(newArb);
      expect(await arbRegistry.isApproved(newArb)).to.be.false;

      await expect(arbRegistry.connect(owner).removeArbitrator(newArb)).to.be.revertedWithCustomError(
        arbRegistry,
        "ArbitratorNotApproved"
      );
    });

    it("Should dispense MockINR faucet and enforce cooldown", async function () {
      const recipient = stranger;
      const balBefore = await mockINR.balanceOf(recipient.address);
      await mockINR.connect(recipient).requestFaucet();
      const balAfter = await mockINR.balanceOf(recipient.address);
      expect(balAfter - balBefore).to.equal(ethers.parseEther("50000"));

      await expect(mockINR.connect(recipient).requestFaucet()).to.be.revertedWithCustomError(
        mockINR,
        "FaucetCooldownActive"
      );
    });
  });


  describe("2. Signing & Deposit Activation (Drafted -> Signed -> Active)", function () {
    let vault: DepositVault;

    beforeEach(async function () {
      vault = await createValidVault();
    });

    it("Should reject sign from unauthorized stranger", async function () {
      await expect(vault.connect(stranger).sign()).to.be.revertedWithCustomError(vault, "Unauthorized");
    });

    it("Should stay Drafted after only one party signs", async function () {
      await vault.connect(landlord).sign();
      expect(await vault.landlordSigned()).to.be.true;
      expect(await vault.tenantSigned()).to.be.false;
      expect(await vault.state()).to.equal(0);
    });

    it("Should transition to Signed when both parties sign", async function () {
      await vault.connect(landlord).sign();
      await expect(vault.connect(tenant).sign())
        .to.emit(vault, "StateChanged")
        .withArgs(0, 1);

      expect(await vault.state()).to.equal(1);
    });

    it("Should reject lockDeposit before Signed state", async function () {
      await mockINR.connect(tenant).approve(await vault.getAddress(), DEPOSIT_AMOUNT);
      await expect(vault.connect(tenant).lockDeposit()).to.be.revertedWithCustomError(vault, "InvalidState");
    });

    it("Should reject lockDeposit from landlord or stranger", async function () {
      await vault.connect(landlord).sign();
      await vault.connect(tenant).sign();

      await expect(vault.connect(landlord).lockDeposit()).to.be.revertedWithCustomError(vault, "Unauthorized");
      await expect(vault.connect(stranger).lockDeposit()).to.be.revertedWithCustomError(vault, "Unauthorized");
    });

    it("Should lock deposit and activate only after move-in evidence is recorded", async function () {
      await vault.connect(landlord).sign();
      await vault.connect(tenant).sign();

      await mockINR.connect(tenant).approve(await vault.getAddress(), DEPOSIT_AMOUNT);
      await expect(vault.connect(tenant).lockDeposit())
        .to.emit(vault, "DepositLocked")
        .withArgs(tenant.address, DEPOSIT_AMOUNT);

      expect(await vault.state()).to.equal(1);

      await expect(vault.connect(landlord).recordMoveInEvidence(MOCK_MOVE_IN_HASH))
        .to.emit(vault, "EvidenceRecorded")
        .withArgs(0, MOCK_MOVE_IN_HASH, landlord.address)
        .and.to.emit(vault, "TenancyActivated")
        .and.to.emit(vault, "StateChanged")
        .withArgs(1, 2);

      expect(await vault.state()).to.equal(2);
      expect(await mockINR.balanceOf(await vault.getAddress())).to.equal(DEPOSIT_AMOUNT);
    });

    it("Should prevent double deposit lock", async function () {
      await vault.connect(landlord).sign();
      await vault.connect(tenant).sign();

      await mockINR.connect(tenant).approve(await vault.getAddress(), DEPOSIT_AMOUNT * 2n);
      await vault.connect(tenant).lockDeposit();

      await expect(vault.connect(tenant).lockDeposit()).to.be.revertedWithCustomError(vault, "InvalidParameters");
    });
  });

  describe("3. MoveOut & Happy Path Auto-Refund via Keeper", function () {
    let vault: DepositVault;

    beforeEach(async function () {
      vault = await createValidVault();
      await vault.connect(landlord).sign();
      await vault.connect(tenant).sign();
      await mockINR.connect(tenant).approve(await vault.getAddress(), DEPOSIT_AMOUNT);
      await vault.connect(tenant).lockDeposit();
      await vault.connect(tenant).recordMoveInEvidence(MOCK_MOVE_IN_HASH);
    });

    it("Should transition from Active to MoveOut and set claim deadline", async function () {
      await expect(vault.connect(landlord).startMoveOut(MOCK_MOVE_OUT_HASH))
        .to.emit(vault, "MoveOutStarted")
        .and.to.emit(vault, "StateChanged")
        .withArgs(2, 3);

      expect(await vault.state()).to.equal(3);
      const deadline = await vault.claimDeadline();
      const now = await time.latest();
      expect(deadline).to.be.closeTo(BigInt(now) + BigInt(CLAIM_WINDOW), 5n);
    });

    it("Should revert finalizeRefund before claim deadline lapses", async function () {
      await vault.connect(landlord).startMoveOut(MOCK_MOVE_OUT_HASH);

      await expect(vault.connect(stranger).finalizeRefund()).to.be.revertedWithCustomError(
        vault,
        "ClaimWindowNotPassed"
      );

      const deadline = await vault.claimDeadline();
      await time.increaseTo(deadline - 2n);

      await expect(vault.connect(stranger).finalizeRefund()).to.be.revertedWithCustomError(
        vault,
        "ClaimWindowNotPassed"
      );
    });

    it("Should allow anyone/keeper to finalizeRefund once deadline passes", async function () {
      await vault.connect(landlord).startMoveOut(MOCK_MOVE_OUT_HASH);
      const deadline = await vault.claimDeadline();

      await time.increaseTo(deadline + 1n);

      const tenantBalBefore = await mockINR.balanceOf(tenant.address);

      await expect(vault.connect(stranger).finalizeRefund())
        .to.emit(vault, "TenancyRefunded")
        .withArgs(DEPOSIT_AMOUNT, 0)
        .and.to.emit(vault, "StateChanged")
        .withArgs(3, 5);

      expect(await vault.state()).to.equal(5);
      const tenantBalAfter = await mockINR.balanceOf(tenant.address);
      expect(tenantBalAfter - tenantBalBefore).to.equal(DEPOSIT_AMOUNT);
      expect(await mockINR.balanceOf(await vault.getAddress())).to.equal(0n);
    });
  });

  describe("4. Disputed Claims & Arbitration", function () {
    let vault: DepositVault;

    beforeEach(async function () {
      vault = await createValidVault();
      await vault.connect(landlord).sign();
      await vault.connect(tenant).sign();
      await mockINR.connect(tenant).approve(await vault.getAddress(), DEPOSIT_AMOUNT);
      await vault.connect(tenant).lockDeposit();
      await vault.connect(tenant).recordMoveInEvidence(MOCK_MOVE_IN_HASH);
      await vault.connect(landlord).startMoveOut(MOCK_MOVE_OUT_HASH);
    });

    it("Should reject claim exceeding deduction cap (NFR-S-4, BR-4)", async function () {
      const overCap = DEDUCTION_CAP + ethers.parseEther("100");
      await expect(
        vault.connect(landlord).raiseClaim(overCap, "QmExceededCapReference")
      ).to.be.revertedWithCustomError(vault, "ExceedsDeductionCap").withArgs(overCap, DEDUCTION_CAP);
    });

    it("Should reject claim from tenant or stranger", async function () {
      await expect(
        vault.connect(tenant).raiseClaim(DEDUCTION_CAP, "QmTenantRef")
      ).to.be.revertedWithCustomError(vault, "Unauthorized");

      await expect(
        vault.connect(stranger).raiseClaim(DEDUCTION_CAP, "QmStrangerRef")
      ).to.be.revertedWithCustomError(vault, "Unauthorized");
    });

    it("Should reject claim after claim window deadline has passed", async function () {
      const deadline = await vault.claimDeadline();
      await time.increaseTo(deadline + 10n);

      await expect(
        vault.connect(landlord).raiseClaim(DEDUCTION_CAP, "QmLateClaim")
      ).to.be.revertedWithCustomError(vault, "ClaimWindowPassed");
    });

    it("Should allow valid landlord claim within cap and transition to Disputed", async function () {
      const claimAmount = ethers.parseEther("15000");
      await expect(vault.connect(landlord).raiseClaim(claimAmount, "QmDamageInspectionReport"))
        .to.emit(vault, "ClaimRaised")
        .withArgs(claimAmount, "QmDamageInspectionReport")
        .and.to.emit(vault, "StateChanged")
        .withArgs(3, 4);

      expect(await vault.state()).to.equal(4);
      expect(await vault.claimedAmount()).to.equal(claimAmount);
    });

    it("Should allow tenant to accept claim directly without arbitration (TBD-3)", async function () {
      const claimAmount = ethers.parseEther("15000");
      await vault.connect(landlord).raiseClaim(claimAmount, "QmDamageReport");

      const landlordBalBefore = await mockINR.balanceOf(landlord.address);
      const tenantBalBefore = await mockINR.balanceOf(tenant.address);

      await expect(vault.connect(tenant).acceptClaim())
        .to.emit(vault, "ClaimAcceptedByTenant")
        .withArgs(claimAmount, DEPOSIT_AMOUNT - claimAmount)
        .and.to.emit(vault, "StateChanged")
        .withArgs(4, 5);

      expect(await vault.state()).to.equal(5);
      expect(await mockINR.balanceOf(landlord.address) - landlordBalBefore).to.equal(claimAmount);
      expect(await mockINR.balanceOf(tenant.address) - tenantBalBefore).to.equal(DEPOSIT_AMOUNT - claimAmount);
      expect(await mockINR.balanceOf(await vault.getAddress())).to.equal(0n);
    });

    it("Should allow assigned arbitrator to decide valid split", async function () {
      const claimAmount = ethers.parseEther("15000");
      await vault.connect(landlord).raiseClaim(claimAmount, "QmDamageReport");

      await expect(vault.connect(owner).assignArbitrator(arbitrator.address))
        .to.emit(vault, "ArbitratorAssigned")
        .withArgs(arbitrator.address);

      const landlordAward = ethers.parseEther("12000");
      const tenantRefund = DEPOSIT_AMOUNT - landlordAward;

      const landlordBalBefore = await mockINR.balanceOf(landlord.address);
      const tenantBalBefore = await mockINR.balanceOf(tenant.address);

      await expect(vault.connect(arbitrator).decide(landlordAward, tenantRefund))
        .to.emit(vault, "DisputeDecided")
        .withArgs(arbitrator.address, landlordAward, tenantRefund)
        .and.to.emit(vault, "StateChanged")
        .withArgs(4, 5);

      expect(await mockINR.balanceOf(landlord.address) - landlordBalBefore).to.equal(landlordAward);
      expect(await mockINR.balanceOf(tenant.address) - tenantBalBefore).to.equal(tenantRefund);
      expect(await mockINR.balanceOf(await vault.getAddress())).to.equal(0n);
    });

    it("Should reject decision where sum of payouts does not equal deposit amount (Invariant)", async function () {
      await vault.connect(landlord).raiseClaim(DEDUCTION_CAP, "QmReport");
      await vault.connect(owner).assignArbitrator(arbitrator.address);

      await expect(
        vault.connect(arbitrator).decide(ethers.parseEther("10000"), ethers.parseEther("30000"))
      ).to.be.revertedWithCustomError(vault, "InvalidSettlementSplit");
    });

    it("Should reject decision where landlord award exceeds deduction cap (Invariant)", async function () {
      await vault.connect(landlord).raiseClaim(DEDUCTION_CAP, "QmReport");
      await vault.connect(owner).assignArbitrator(arbitrator.address);

      const overCapAward = DEDUCTION_CAP + ethers.parseEther("1000");
      const tenantRefund = DEPOSIT_AMOUNT - overCapAward;

      await expect(
        vault.connect(arbitrator).decide(overCapAward, tenantRefund)
      ).to.be.revertedWithCustomError(vault, "ExceedsDeductionCap");
    });

    it("Should trigger 30-day arbitrator inactivity fallback refund to tenant (TBD-11)", async function () {
      await vault.connect(landlord).raiseClaim(DEDUCTION_CAP, "QmReport");
      const disputeTime = await time.latest();

      await expect(vault.connect(tenant).finalizeRefund()).to.be.revertedWithCustomError(
        vault,
        "ArbitratorInactivityTimeoutNotPassed"
      );

      await time.increaseTo(disputeTime + 30 * 24 * 60 * 60 + 10);

      const tenantBalBefore = await mockINR.balanceOf(tenant.address);
      await expect(vault.connect(tenant).finalizeRefund())
        .to.emit(vault, "TenancyRefunded")
        .withArgs(DEPOSIT_AMOUNT, 0)
        .and.to.emit(vault, "StateChanged")
        .withArgs(4, 5);

      expect(await vault.state()).to.equal(5);
      expect(await mockINR.balanceOf(tenant.address) - tenantBalBefore).to.equal(DEPOSIT_AMOUNT);
    });
  });

  describe("5. Safety & Invariant Tests (NFR-S-1 to S-4)", function () {
    it("Cannot re-initialize a deployed vault clone", async function () {
      const vault = await createValidVault();
      await expect(
        vault.initialize(
          landlord.address,
          tenant.address,
          await mockINR.getAddress(),
          DEPOSIT_AMOUNT,
          DEDUCTION_CAP,
          CLAIM_WINDOW,
          MOCK_LEASE_HASH,
          await idRegistry.getAddress(),
          await arbRegistry.getAddress(),
          owner.address
        )
      ).to.be.revertedWithCustomError(vault, "AlreadyInitialized");
    });

    it("Cannot directly initialize master template", async function () {
      await expect(
        vaultImplementation.initialize(
          landlord.address,
          tenant.address,
          await mockINR.getAddress(),
          DEPOSIT_AMOUNT,
          DEDUCTION_CAP,
          CLAIM_WINDOW,
          MOCK_LEASE_HASH,
          await idRegistry.getAddress(),
          await arbRegistry.getAddress(),
          owner.address
        )
      ).to.be.revertedWithCustomError(vaultImplementation, "AlreadyInitialized");
    });

    it("Funds are completely preserved across all payout pathways with zero dust", async function () {
      const vault = await createValidVault();
      await vault.connect(landlord).sign();
      await vault.connect(tenant).sign();
      await mockINR.connect(tenant).approve(await vault.getAddress(), DEPOSIT_AMOUNT);
      await vault.connect(tenant).lockDeposit();
      await vault.connect(tenant).recordMoveInEvidence(MOCK_MOVE_IN_HASH);
      await vault.connect(landlord).startMoveOut(MOCK_MOVE_OUT_HASH);
      await vault.connect(landlord).raiseClaim(DEDUCTION_CAP, "QmRef");
      await vault.connect(owner).assignArbitrator(arbitrator.address);

      const landlordAmt = ethers.parseEther("18432.50");
      const tenantAmt = DEPOSIT_AMOUNT - landlordAmt;

      await vault.connect(arbitrator).decide(landlordAmt, tenantAmt);
      expect(await mockINR.balanceOf(await vault.getAddress())).to.equal(0n);
    });
  });
});
