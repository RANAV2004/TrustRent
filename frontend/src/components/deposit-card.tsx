"use client";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { ConditionPhotos } from "@/components/condition-photos";
import { Deposit, networkLabel, proposeSettlement, respondToSettlement, STATUS_LABEL } from "@/lib/deposits";
import { formatINR } from "@/lib/format";
const date = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }) : "";
const tone: Record<Deposit["status"], string> = {
  held: "bg-vault-soft text-vault",
  settlement_proposed: "bg-amber-soft text-amber",
  disputed: "bg-claim-soft text-claim",
  settled: "bg-mist text-ink",
};
export function Hash({ label, value, href }: { label: string; value: string | null; href?: string | null }) { // hash
  const [copied, setCopied] = useState(false);
  if (!value) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted">{label}</span>
      <span className="flex flex-wrap items-center gap-2">
        <code className="break-all rounded bg-mist px-1.5 py-0.5 text-xs">{value}</code>
        <button type="button" className="text-xs text-vault hover:underline"
          onClick={() => navigator.clipboard?.writeText(value).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); })}>
          {copied ? "Copied" : "Copy"}
        </button>
        {href && <a href={href} target="_blank" rel="noopener noreferrer" className="text-xs text-vault hover:underline">View on explorer</a>}
      </span>
    </div>
  );
}
export function VerifiedBadge({ d }: { d: Deposit }) { // verified badge
  if (!d.verification) return null;
  return d.verification.verified ? (
    <p className="rounded-lg bg-vault-soft px-3 py-2 text-sm text-vault">
      Verified: these details match the receipt{d.receipt.network === "polygon-amoy" ? " on the Polygon blockchain" : " in the TrustRent ledger"}.
    </p>
  ) : (
    <p role="alert" className="rounded-lg bg-claim-soft px-3 py-2 text-sm text-claim">
      Mismatch: the stored details no longer match the receipt{d.verification.ledgerIntact ? "" : ", and the ledger chain is broken"}. Contact TrustRent.
    </p>
  );
}
export function DepositCard({ d, onChange, highlight = false }: { d: Deposit; onChange: (d: Deposit) => void; highlight?: boolean }) { // deposit card
  const [deducted, setDeducted] = useState("0");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function act(fn: () => Promise<Deposit>) {
    setBusy(true);
    setError(null);
    try {
      onChange(await fn());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }
  function propose(e: FormEvent) {
    e.preventDefault();
    act(() => proposeSettlement(d.id, Number(deducted) || 0, reason));
  }
  const settledLike = d.status === "settlement_proposed" || d.status === "settled";
  return (
    <article id={d.id} className={`flex flex-col gap-4 rounded-2xl border bg-surface p-5 ${highlight ? "border-vault ring-2 ring-vault/20" : "border-line"}`}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs text-muted">Deposit {d.id}</p>
          <Link href={`/listings/${d.listing.id}`} className="text-lg font-medium hover:underline">{d.listing.title}</Link>
          <p className="text-sm text-muted">{d.listing.area}</p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${tone[d.status]}`}>{STATUS_LABEL[d.status]}</span>
      </header>
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div><dt className="text-muted">Deposited</dt><dd className="font-semibold tabular">{formatINR(d.amount)}</dd></div>
        <div><dt className="text-muted">Paid on</dt><dd>{date(d.paidAt)}</dd></div>
        {settledLike && <div><dt className="text-muted">Deducted</dt><dd className="font-semibold tabular">{formatINR(d.deducted ?? 0)}</dd></div>}
        {settledLike && <div><dt className="text-muted">Refund to tenant</dt><dd className="font-semibold tabular text-vault">{formatINR(d.refunded ?? 0)}</dd></div>}
        {d.tenant && <div><dt className="text-muted">Tenant</dt><dd>{d.tenant.name}</dd></div>}
        {d.owner && <div><dt className="text-muted">Owner</dt><dd>{d.owner.name}</dd></div>}
        {d.payment?.reference && (
          <div className="col-span-2">
            <dt className="text-muted">{d.payment.provider === "manual" ? "Transaction ID (recorded by TrustRent)" : "Payment ID"}</dt>
            <dd className="break-all">{d.payment.reference}</dd>
          </div>
        )}
        {d.settledAt && <div><dt className="text-muted">Settled on</dt><dd>{date(d.settledAt)}</dd></div>}
        {d.ownerPayout && <div><dt className="text-muted">Owner payout</dt><dd>{d.ownerPayout === "paid" ? "Paid" : "Due"}</dd></div>}
      </dl>
      {d.reason && <p className="rounded-lg bg-mist px-3 py-2 text-sm"><span className="font-medium">Reason for deduction:</span> {d.reason}</p>}
      <div className="flex flex-col gap-2 border-t border-line pt-3">
        <p className="text-sm font-medium">Receipt, {networkLabel(d.receipt.network)}</p>
        <Hash label="Deposit receipt" value={d.receipt.recordTx} href={d.receipt.recordUrl} />
        <Hash label="Settlement receipt" value={d.receipt.settleTx} href={d.receipt.settleUrl} />
        <p className="text-xs text-muted">Keep the deposit ID or receipt hash. Anyone with an account can check it on <Link href={`/deposits/lookup?q=${d.id}`} className="text-vault hover:underline">Look up deposit</Link>.</p>
      </div>
      <VerifiedBadge d={d} />
      {d.role && <ConditionPhotos depositId={d.id} />}
      {d.role === "owner" && (d.status === "held" || d.status === "settlement_proposed") && (
        <form onSubmit={propose} className="flex flex-col gap-3 rounded-xl bg-mist p-4">
          <p className="text-sm font-medium">{d.status === "held" ? "Tenant moved out? Propose the settlement" : "Change your proposal"}</p>
          <div className="grid gap-3 sm:grid-cols-[160px_minmax(0,1fr)]">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-xs text-muted">Deduct (₹)</span>
              <input inputMode="numeric" value={deducted} onChange={(e) => setDeducted(e.target.value.replace(/\D/g, ""))} className="rounded-lg border border-line bg-surface px-3 py-2" />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-xs text-muted">Reason (needed if you deduct anything)</span>
              <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Broken bathroom tile, ₹1,800 repair bill" className="rounded-lg border border-line bg-surface px-3 py-2" />
            </label>
          </div>
          <p className="text-xs text-muted">Refund to tenant: {formatINR(Math.max(0, d.amount - (Number(deducted) || 0)))}. The tenant must accept before anything is paid out.</p>
          <button type="submit" disabled={busy} className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">Send proposal</button>
        </form>
      )}
      {d.role === "tenant" && d.status === "settlement_proposed" && (
        <div className="flex flex-col gap-2 rounded-xl bg-amber-soft p-4">
          <p className="text-sm font-medium">The owner proposes deducting {formatINR(d.deducted ?? 0)} and refunding {formatINR(d.refunded ?? 0)}.</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={busy} onClick={() => act(() => respondToSettlement(d.id, true))} className="rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep">Accept and settle</button>
            <button type="button" disabled={busy} onClick={() => act(() => respondToSettlement(d.id, false))} className="rounded-lg border border-claim/40 px-4 py-2 text-sm text-claim hover:bg-claim-soft">Dispute: ask TrustRent to decide</button>
          </div>
        </div>
      )}
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
    </article>
  );
}