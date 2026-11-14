import asyncio
import json
import logging
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.deposits import ConditionPhoto, Deposit, LedgerEntry
from app.models.marketplace import utcnow
from app.services import chain
from app.services.accounts import iso
from app.services.hash_service import HashService
GENESIS = "0x" + "0" * 64
LEDGER_LOCK_ID = 7_242_011  # Postgres advisory lock: one ledger writer at a time
_local_lock = asyncio.Lock()
log = logging.getLogger(__name__)
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
    if db.bind.dialect.name == "postgresql":  # held until this transaction commits, so no two blocks share a parent
        await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": LEDGER_LOCK_ID})
    async with _local_lock:  # SQLite / single process; ux_ledger_prev_hash is the final guard
        return await _append_locked(db, deposit_id, kind, data_hash, amounts)


async def _append_locked(db: AsyncSession, deposit_id: str, kind: str, data_hash: str, amounts: dict) -> LedgerEntry:
    last = await db.scalar(select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(1))
    prev = last.entry_hash if last else GENESIS
    at = utcnow()
    e = LedgerEntry(deposit_id=deposit_id, kind=kind, amounts=amounts, data_hash=data_hash, prev_hash=prev,
                    entry_hash=_entry_hash(prev, kind, deposit_id, data_hash, amounts, iso(at)), created_at=at)
    db.add(e)
    await db.flush()
    return e
async def record_deposit(db: AsyncSession, d: Deposit) -> None:  # on-chain copy is added later by anchor_pending
    d.record_hash = fingerprint(deposit_details(d))
    entry = await _append(db, d.id, "deposit", d.record_hash, {"amount": d.amount})
    d.record_tx = entry.entry_hash
    d.network = "trustrent-ledger"
async def record_settlement(db: AsyncSession, d: Deposit) -> None:
    d.settle_hash = fingerprint(settlement_details(d))
    entry = await _append(db, d.id, "settlement", d.settle_hash, {"deducted": d.deducted, "refunded": d.refunded})
    d.settle_tx = entry.entry_hash
async def record_event(db: AsyncSession, deposit_id: str, kind: str, details: dict) -> LedgerEntry:  # agreements etc.
    return await _append(db, deposit_id, kind, fingerprint(details), {})
async def anchor_pending(db: AsyncSession, limit: int = 20) -> int:
    """Copy deposit and settlement blocks to the blockchain, outside any user request. Safe to retry."""
    if not chain.enabled():
        return 0
    done = 0
    rows = list(await db.scalars(select(LedgerEntry).where(LedgerEntry.chain_tx.is_(None),
                                                           LedgerEntry.kind.in_(("deposit", "settlement")))
                                 .order_by(LedgerEntry.seq).limit(limit)))
    for e in rows:
        d = await db.get(Deposit, e.deposit_id)
        if not d:
            continue
        try:
            if e.kind == "deposit":
                existing = await chain.read_deposit(d.id)
                tx = "0x-recorded" if existing else await chain.record_deposit(d.id, d.amount, d.record_hash)
            else:
                if d.network == "trustrent-ledger":
                    continue  # its deposit block isn't on-chain yet
                tx = await chain.settle_deposit(d.id, d.deducted or 0, d.refunded or 0, d.settle_hash)
        except Exception as ex:  # noqa: BLE001 - try again next round
            log.warning("Anchoring %s block %s failed: %s", e.kind, e.seq, ex)
            break
        if not tx:
            continue
        e.chain_tx = tx if tx.startswith("0x") and len(tx) == 66 else e.entry_hash
        if e.kind == "deposit":
            d.network = chain.network_name()
            if len(tx) == 66:
                d.record_tx = tx
        elif len(tx) == 66:
            d.settle_tx = tx
        await db.commit()
        done += 1
    return done
def photo_details(p: ConditionPhoto) -> dict:
    return {"photoId": p.id, "depositId": p.deposit_id, "side": p.side, "stage": p.stage, "room": p.room,
            "fileHash": p.file_hash, "uploadedAt": iso(p.created_at)}
async def record_photo(db: AsyncSession, p: ConditionPhoto) -> None:  # photo block
    p.record_hash = fingerprint(photo_details(p))
    entry = await _append(db, p.deposit_id, "photo", p.record_hash, {})
    p.record_tx = entry.entry_hash
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