import { expect } from "chai";
import { ethers } from "hardhat";
describe("DepositRegistry", () => {
  const id = ethers.id("DEP-0001");
  const dataHash = ethers.id("deposit-details");
  const settleHash = ethers.id("settlement-details");
  async function deploy() {
    const [owner, other] = await ethers.getSigners();
    const Registry = await ethers.getContractFactory("DepositRegistry");
    const registry = await Registry.deploy(owner.address);
    return { registry, owner, other };
  }
  it("records a deposit once and reads it back", async () => {
    const { registry } = await deploy();
    await expect(registry.recordDeposit(id, 40000, dataHash)).to.emit(registry, "DepositRecorded").withArgs(id, 40000, dataHash);
    const r = await registry.getDeposit(id);
    expect(r.amount).to.equal(40000n);
    expect(r.dataHash).to.equal(dataHash);
    expect(r.settled).to.equal(false);
    await expect(registry.recordDeposit(id, 40000, dataHash)).to.be.revertedWithCustomError(registry, "AlreadyRecorded");
  });
  it("settles with a split that adds up to the deposit, only once", async () => {
    const { registry } = await deploy();
    await registry.recordDeposit(id, 40000, dataHash);
    await expect(registry.settleDeposit(id, 5000, 30000, settleHash)).to.be.revertedWithCustomError(registry, "InvalidSplit");
    await expect(registry.settleDeposit(id, 5000, 35000, settleHash)).to.emit(registry, "DepositSettled");
    const r = await registry.getDeposit(id);
    expect(r.settled).to.equal(true);
    expect(r.refunded).to.equal(35000n);
    await expect(registry.settleDeposit(id, 0, 40000, settleHash)).to.be.revertedWithCustomError(registry, "AlreadySettled");
  });
  it("rejects unknown deposits and non-owners", async () => {
    const { registry, other } = await deploy();
    await expect(registry.settleDeposit(id, 0, 1, settleHash)).to.be.revertedWithCustomError(registry, "UnknownDeposit");
    await expect(registry.connect(other).recordDeposit(id, 1, dataHash)).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
  });
});
