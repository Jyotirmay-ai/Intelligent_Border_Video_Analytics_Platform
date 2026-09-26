const fs = require("fs");
const path = require("path");

async function main() {
  const EvidenceAnchor = await ethers.getContractFactory("EvidenceAnchor");
  console.log("Deploying EvidenceAnchor...");

  const contract = await EvidenceAnchor.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log(`EvidenceAnchor deployed to: ${address}`);

  // Write the address to a file the Python worker can read
  const outPath = path.join(
    __dirname,
    "..",
    "..",
    "modules",
    "blockchain-evidence-ledger",
    "contract_address.txt"
  );
  fs.writeFileSync(outPath, address, "utf-8");
  console.log(`Contract address written to: ${outPath}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
