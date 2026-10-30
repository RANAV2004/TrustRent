import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.deposits import Deposit, LedgerEntry
from app.models.marketplace import utcnow
from app.services import chain
from app.services.accounts import iso
from app.services.hash_service import HashService
GENESIS = "0x" + "0" * 64
def fingerprint(data: dict) -> str:
    return HashService.hash_text(json.dumps(data, sort_keys=True, separators=(",", ":")))
def deposit_details(d: Deposit) -> dict:
    return {"depositId": d.id, "listingId": d.listing_id, "tenantId": d.tenant_id, "ownerId": d.owner_id,
            "amount": d.amount, "currency": "INR", "paidAt": iso(d.paid_at), "paymentId": d.payment_id}
def settlement_details(d: Deposit) -> dict:
    return {"depositId": d.id, "deducted": d.deducted, "refunded": d.refunded, "reason": d.deduction_reason or "",
            "settledAt": iso(d.settled_at), "settledBy": d.settled_by}
def _entry_hash(prev: str, kind: str, deposit_id: str, data_hash: str, amounts: dict, at: str) -> str:
    return HashService.hash_text("|".join([prev, kind, deposit_id, data_hash, json.dumps(amounts, sort_keys=True), at]))
async def _append(db: AsyncSession, deposit_id: str, kind: str, data_hash: str, amounts: dict) -> LedgerEntry:
    last = await db.scalar(select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(1))
    prev = last.entry_hash if last else GENESIS
    at = utcnow()
    e = LedgerEntry(deposit_id=deposit_id, kind=kind, amounts=amounts, data_hash=data_hash, prev_hash=prev,
                    entry_hash=_entry_hash(prev, kind, deposit_id, data_hash, amounts, iso(at)), created_at=at)
    db.add(e)
    await db.flush()
    return e
async def record_deposit(db: AsyncSession, d: Deposit) -> None:
    d.record_hash = fingerprint(deposit_details(d))
    entry = await _append(db, d.id, "deposit", d.record_hash, {"amount": d.amount})
    tx = await chain.record_deposit(d.id, d.amount, d.record_hash)
    entry.chain_tx = tx
    d.record_tx = tx or entry.entry_hash
    d.network = chain.network_name() if tx else "trustrent-ledger"
async def record_settlement(db: AsyncSession, d: Deposit) -> None:
    d.settle_hash = fingerprint(settlement_details(d))
    entry = await _append(db, d.id, "settlement", d.settle_hash, {"deducted": d.deducted, "refunded": d.refunded})
    tx = await chain.settle_deposit(d.id, d.deducted, d.refunded, d.settle_hash)
    entry.chain_tx = tx
    d.settle_tx = tx or entry.entry_hash
async def ledger_state(db: AsyncSession) -> tuple[list[LedgerEntry], bool]:
    entries = list(await db.scalars(select(LedgerEntry).order_by(LedgerEntry.seq)))
    prev = GENESIS
    for e in entries:
        if e.prev_hash != prev or e.entry_hash != _entry_hash(e.prev_hash, e.kind, e.deposit_id, e.data_hash, e.amounts, iso(e.created_at)):
            return entries, False
        prev = e.entry_hash
    return entries, True
async def verify(db: AsyncSession, d: Deposit, state: tuple[list[LedgerEntry], bool] | None = None) -> dict:
    entries, chain_ok = state or await ledger_state(db)
    mine = [e for e in entries if e.deposit_id == d.id]
    dep_entry = next((e for e in mine if e.kind == "deposit"), None)
    set_entry = next((e for e in mine if e.kind == "settlement"), None)
    details_ok = bool(dep_entry and dep_entry.data_hash == fingerprint(deposit_details(d)))
    if d.status == "settled":
        details_ok = details_ok and bool(set_entry and set_entry.data_hash == fingerprint(settlement_details(d)))
    onchain = await chain.read_deposit(d.id) if d.network and d.network != "trustrent-ledger" else None
    if onchain is not None:
        details_ok = details_ok and onchain.get("dataHash") == d.record_hash
    return {"ledgerIntact": chain_ok, "detailsMatch": details_ok, "verified": chain_ok and details_ok,
            "onChain": onchain is not None}
