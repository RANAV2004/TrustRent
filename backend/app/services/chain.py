import asyncio
from web3 import Web3
from app.core.config import settings
ABI = [
    {"type": "function", "name": "recordDeposit", "stateMutability": "nonpayable", "outputs": [],
     "inputs": [{"name": "depositId", "type": "bytes32"}, {"name": "amount", "type": "uint256"},
                {"name": "dataHash", "type": "bytes32"}]},
    {"type": "function", "name": "settleDeposit", "stateMutability": "nonpayable", "outputs": [],
     "inputs": [{"name": "depositId", "type": "bytes32"}, {"name": "deducted", "type": "uint256"},
                {"name": "refunded", "type": "uint256"}, {"name": "settlementHash", "type": "bytes32"}]},
    {"type": "function", "name": "getDeposit", "stateMutability": "view",
     "inputs": [{"name": "depositId", "type": "bytes32"}],
     "outputs": [{"name": "amount", "type": "uint256"}, {"name": "dataHash", "type": "bytes32"},
                 {"name": "recordedAt", "type": "uint256"}, {"name": "settled", "type": "bool"},
                 {"name": "deducted", "type": "uint256"}, {"name": "refunded", "type": "uint256"},
                 {"name": "settlementHash", "type": "bytes32"}, {"name": "settledAt", "type": "uint256"}]},
]
def enabled() -> bool:
    return bool(settings.DEPOSIT_REGISTRY_ADDRESS and settings.CHAIN_SIGNER_PRIVATE_KEY and settings.POLYGON_AMOY_RPC_URL)
def network_name() -> str:
    return "polygon-amoy" if settings.CHAIN_ID == 80002 else f"chain-{settings.CHAIN_ID}"
def deposit_key(deposit_id: str) -> bytes:
    return Web3.keccak(text=deposit_id)
def _contract():
    w3 = Web3(Web3.HTTPProvider(settings.POLYGON_AMOY_RPC_URL, request_kwargs={"timeout": 30}))
    return w3, w3.eth.contract(address=Web3.to_checksum_address(settings.DEPOSIT_REGISTRY_ADDRESS), abi=ABI)
def _send(fn_name: str, *args) -> str:
    w3, c = _contract()
    acct = w3.eth.account.from_key(settings.CHAIN_SIGNER_PRIVATE_KEY)
    tx = getattr(c.functions, fn_name)(*args).build_transaction({
        "from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address, "pending"),
        "chainId": settings.CHAIN_ID,
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt.status != 1:
        raise RuntimeError(f"{fn_name} reverted on-chain")
    return Web3.to_hex(tx_hash)
async def record_deposit(deposit_id: str, amount: int, data_hash: str) -> str | None:
    if not enabled():
        return None
    return await asyncio.to_thread(_send, "recordDeposit", deposit_key(deposit_id), amount, bytes.fromhex(data_hash[2:]))
async def settle_deposit(deposit_id: str, deducted: int, refunded: int, settlement_hash: str) -> str | None:
    if not enabled():
        return None
    return await asyncio.to_thread(_send, "settleDeposit", deposit_key(deposit_id), deducted, refunded,
                                   bytes.fromhex(settlement_hash[2:]))
def _read(deposit_id: str) -> dict | None:
    _, c = _contract()
    r = c.functions.getDeposit(deposit_key(deposit_id)).call()
    if r[2] == 0:
        return None
    return {"amount": r[0], "dataHash": Web3.to_hex(r[1]), "recordedAt": r[2], "settled": r[3],
            "deducted": r[4], "refunded": r[5], "settlementHash": Web3.to_hex(r[6]), "settledAt": r[7]}
async def read_deposit(deposit_id: str) -> dict | None:
    if not enabled():
        return None
    try:
        return await asyncio.to_thread(_read, deposit_id)
    except Exception:  # noqa: BLE001
        return None
