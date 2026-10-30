import os
import json
import shutil
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.main import app
from app.core.errors import ERROR_CATALOG

HAND_OFF_DIR = ROOT_DIR / "docs" / "hand_off"
CONTRACTS_HAND_OFF_DIR = HAND_OFF_DIR / "contracts"
ABIS_DIR = CONTRACTS_HAND_OFF_DIR / "abis"

def generate_hand_offs():
    HAND_OFF_DIR.mkdir(parents=True, exist_ok=True)
    ABIS_DIR.mkdir(parents=True, exist_ok=True)

    print("1. Generating OpenAPI spec...")
    openapi_schema = app.openapi()
    with open(HAND_OFF_DIR / "openapi.json", "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)

    print("2. Copying ABIs...")
    artifacts_dir = ROOT_DIR / "contracts" / "artifacts" / "contracts"
    contract_names = ["DepositVault", "TenancyFactory", "IdentityRegistry", "ArbitratorRegistry", "MockINR"]
    
    for name in contract_names:
        json_file = artifacts_dir / f"{name}.sol" / f"{name}.json"
        if json_file.exists():
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            with open(ABIS_DIR / f"{name}.json", "w", encoding="utf-8") as f:
                json.dump(data.get("abi", []), f, indent=2)

    print("3. Exporting addresses.json...")
    addr_file = ROOT_DIR / "contracts" / "addresses.json"
    if addr_file.exists():
        shutil.copy(addr_file, CONTRACTS_HAND_OFF_DIR / "addresses.json")
    else:
        default_addrs = {
            "chainId": 31337,
            "network": "hardhat_localhost",
            "contracts": {
                "MockINR": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
                "IdentityRegistry": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
                "ArbitratorRegistry": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
                "DepositVaultTemplate": "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9",
                "TenancyFactory": "0xDc64a140Aa3E981100a9becA4E685f962f0cF6C9"
            }
        }
        with open(CONTRACTS_HAND_OFF_DIR / "addresses.json", "w", encoding="utf-8") as f:
            json.dump(default_addrs, f, indent=2)

    print("4. Copying GraphQL schema...")
    subgraph_schema = ROOT_DIR / "subgraph" / "schema.graphql"
    if subgraph_schema.exists():
        shutil.copy(subgraph_schema, HAND_OFF_DIR / "schema.graphql")

    print("5. Generating Error Catalog markdown...")
    error_md = ["# TrustRent Error Catalog for Frontend UI Mapping\n\n| Error Code | Revert Name | User-Facing Plain Title | Plain Language Message |\n|---|---|---|---|"]
    for name, item in ERROR_CATALOG.items():
        error_md.append(f"| `{item['code']}` | `{name}` | **{item['title']}** | {item['message']} |")
    
    with open(HAND_OFF_DIR / "error_catalog.md", "w", encoding="utf-8") as f:
        f.write("\n".join(error_md))

    print("6. Generating State & Action Matrix...")
    matrix_md = """# TrustRent State & Action Matrix (Frontend Hand-Off)

This matrix defines what information and user action buttons must be rendered on the Tenant, Landlord, and Arbitrator dashboards for each lifecycle state.

| State | Tenant View & Actions | Landlord View & Actions | Arbitrator View & Actions |
|---|---|---|---|
| **Drafted** | Review anchored lease terms; **Sign Lease** button (`sign()`). | View status; **Sign Lease** button (`sign()`). | Read-only view (inactive). |
| **Signed** | **Lock Deposit** button (`lockDeposit()`); **Upload Move-In Evidence** (`recordMoveInEvidence()`). | **Upload Move-In Evidence** (`recordMoveInEvidence()`); awaiting tenant deposit. | Read-only view (inactive). |
| **Active** | View lease details; live countdown to lease end; upload additional condition notes. | View lease details; live countdown to lease end; upload additional condition notes. | Read-only view (inactive). |
| **MoveOut** | Upload move-out evidence; view live countdown timer for landlord claim window; **Trigger Autonomous Refund** button (`finalizeRefund()`) enabled post-deadline. | Upload move-out evidence; **Submit Capped Claim** button (`raiseClaim()`) enabled within window. | Read-only view (inactive). |
| **Disputed** | View landlord claim and proof evidence; **Accept Claim** button (`acceptClaim()`) to settle directly without arbitration. | View dispute status; awaiting arbitrator ruling or tenant direct acceptance. | **Review Evidence Manifests**; verify hash match status; **Submit Binding Decision** split (`decide()`). |
| **Refunded** | View historical transaction log, settlement split, and refunded token receipts. | View historical transaction log, settlement split, and deduction receipts. | View executed split decision record and case closed status. |
"""
    with open(HAND_OFF_DIR / "state_action_matrix.md", "w", encoding="utf-8") as f:
        f.write(matrix_md)

    print("7. Generating Interface Freeze v1.0...")
    freeze_md = """# TrustRent Interface Freeze v1.0

**Effective Date:** October 27, 2026  
**Status:** FROZEN v1.0  
**Scope:** Smart Contract ABIs, OpenAPI REST Specification, Subgraph GraphQL Schema, and Error Catalog.

### Change Management Policy
Per Plan Section 6, all interfaces are now frozen at v1.0. Any breaking changes require a formal pull request modifying these interface documents and explicit coordination across both backend/blockchain and frontend teams.

### Frozen Artifact Links
- **OpenAPI Draft & REST Endpoints:** [`openapi.json`](./openapi.json)
- **Contract ABIs & TypeChain Types:** [`contracts/abis/`](./contracts/abis/)
- **Network Deployment Addresses:** [`contracts/addresses.json`](./contracts/addresses.json)
- **Indexer GraphQL Schema:** [`schema.graphql`](./schema.graphql)
- **User-Facing Error Catalog:** [`error_catalog.md`](./error_catalog.md)
- **UI State & Action Matrix:** [`state_action_matrix.md`](./state_action_matrix.md)
"""
    with open(HAND_OFF_DIR / "INTERFACE_FREEZE_v1.0.md", "w", encoding="utf-8") as f:
        f.write(freeze_md)

    print("Frontend hand-off artifacts generation complete!")

if __name__ == "__main__":
    generate_hand_offs()
