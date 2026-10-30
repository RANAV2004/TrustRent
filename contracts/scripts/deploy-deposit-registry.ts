import { ethers } from "hardhat";
async function main() {
  const [deployer] = await ethers.getSigners();
  const Registry = await ethers.getContractFactory("DepositRegistry");
  const registry = await Registry.deploy(deployer.address);
  await registry.waitForDeployment();
  console.log("DepositRegistry deployed at:", await registry.getAddress());
  console.log("Owner (backend signer):", deployer.address);
}
main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
