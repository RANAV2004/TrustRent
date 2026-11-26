import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
  const [deployer] = await ethers.getSigners();
  const network = await ethers.provider.getNetwork();
  console.log(`Deploying TrustRent contracts with account: ${deployer.address} on chainId: ${network.chainId}`);

  const MockINR = await ethers.getContractFactory("MockINR");
  const mockINR = await MockINR.deploy();
  await mockINR.waitForDeployment();
  const mockINRAddress = await mockINR.getAddress();
  console.log("MockINR deployed at:", mockINRAddress);

  const IdentityRegistry = await ethers.getContractFactory("IdentityRegistry");
  const idRegistry = await IdentityRegistry.deploy(deployer.address, deployer.address);
  await idRegistry.waitForDeployment();
  const idRegistryAddress = await idRegistry.getAddress();
  console.log("IdentityRegistry deployed at:", idRegistryAddress);

  const ArbitratorRegistry = await ethers.getContractFactory("ArbitratorRegistry");
  const arbRegistry = await ArbitratorRegistry.deploy(deployer.address);
  await arbRegistry.waitForDeployment();
  const arbRegistryAddress = await arbRegistry.getAddress();
  console.log("ArbitratorRegistry deployed at:", arbRegistryAddress);

  const DepositVault = await ethers.getContractFactory("DepositVault");
  const vaultTemplate = await DepositVault.deploy();
  await vaultTemplate.waitForDeployment();
  const vaultTemplateAddress = await vaultTemplate.getAddress();
  console.log("DepositVault Template deployed at:", vaultTemplateAddress);

  const TenancyFactory = await ethers.getContractFactory("TenancyFactory");
  const factory = await TenancyFactory.deploy(
    vaultTemplateAddress,
    idRegistryAddress,
    arbRegistryAddress
  );
  await factory.waitForDeployment();
  const factoryAddress = await factory.getAddress();
  console.log("TenancyFactory deployed at:", factoryAddress);

  const deployedAddresses = {
    chainId: Number(network.chainId),
    networkName: network.name,
    deployedAt: new Date().toISOString(),
    deployer: deployer.address,
    contracts: {
      MockINR: mockINRAddress,
      IdentityRegistry: idRegistryAddress,
      ArbitratorRegistry: arbRegistryAddress,
      DepositVaultTemplate: vaultTemplateAddress,
      TenancyFactory: factoryAddress
    }
  };

  const outputDir = path.join(__dirname, "../");
  fs.writeFileSync(
    path.join(outputDir, "addresses.json"),
    JSON.stringify(deployedAddresses, null, 2)
  );

  console.log("\nAddresses successfully written to contracts/addresses.json");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
