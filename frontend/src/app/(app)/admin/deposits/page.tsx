"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Loading, PageHeader, Pill, Stat, when } from "@/components/admin-ui";
import { DepositCard } from "@/components/deposit-card";
import { getLedger, LedgerBlock } from "@/lib/admin";
import { adminDeposits, adminRecordDeposit, adminSettle, Deposit, markOwnerPaid, networkLabel } from "@/lib/deposits";
import { ApiError } from "@/lib/api";
import { formatINR } from "@/lib/format";
const short = (h: string) => `${h.slice(0, 10)}...${h.slice(-6)}`;
const STEPS = [
  { t: "Tenant pays", d: "The deposit is paid through the payment gateway (Razorpay) and held. TrustRent never holds it in a wallet." },
  { t: "Fingerprint", d: "The deposit details (ID, home, tenant, owner, amount, time) are hashed with keccak-256. Only this 66-character fingerprint is recorded, so no personal data goes on the chain." },
  { t: "Linked block", d: "The fingerprint is written as a block that also contains the hash of the block before it. Changing any old block breaks every link after it." },
  { t: "Anyone can verify", d: "The lookup page recomputes the fingerprint from today's data and compares it with the receipt. Any edit to the amount or names shows as a mismatch." },
];
function SettleForm({ d, onDone }: { d: Deposit; onDone: (d: Deposit) => void }) {
  const [deducted, setDeducted] = useState(String(d.deducted ?? 0));
  const [reason, setReason] = useState(d.reason ?? "");
  const [error, setError] = useState<string | null>(null);
  return (
    <form className="flex flex-col gap-2 rounded-xl border border-dashed border-line p-4"
      onSubmit={(e) => { e.preventDefault(); setError(null); adminSettle(d.id, Number(deducted) || 0, reason).then(onDone, (x) => setError(x.message)); }}>
      <p className="text-sm font-medium">Admin decision</p>
      <div className="grid gap-2 sm:grid-cols-[140px_minmax(0,1fr)_auto]">
        <input aria-label="Deduct (₹)" inputMode="numeric" value={deducted} onChange={(e) => setDeducted(e.target.value.replace(/\D/g, ""))} className="rounded-lg border border-line px-3 py-2 text-sm" />
        <input aria-label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason for the decision" className="rounded-lg border border-line px-3 py-2 text-sm" />
        <button type="submit" className="rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep">Settle</button>
      </div>
      <p className="text-xs text-muted">Refund to tenant: {formatINR(Math.max(0, d.amount - (Number(deducted) || 0)))}. This is final and is written to the receipt.</p>
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
    </form>
  );
}
function GenerateReceipt({ onDone }: { onDone: (d: Deposit) => void }) {
  const [open, setOpen] = useState(false);
  const [v, setV] = useState({ tenant: "", listingId: "", amount: "", transactionId: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof v) => (e: React.ChangeEvent<HTMLInputElement>) => setV((s) => ({ ...s, [k]: e.target.value }));
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!v.tenant.trim()) errs.tenant = "Enter the tenant's username, user ID or email.";
    if (!v.listingId.trim()) errs.listingId = "Enter the home ID, e.g. IND-VN-101.";
    if (!(Number(v.amount) > 0)) errs.amount = "Enter the deposit amount in rupees.";
    if (v.transactionId.trim().length < 4) errs.transactionId = "Enter the bank, UPI or cheque reference.";
    setErrors(errs);
    setFormError(null);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      const d = await adminRecordDeposit({ tenant: v.tenant.trim(), listingId: v.listingId.trim(), amount: Number(v.amount), transactionId: v.transactionId.trim() });
      onDone(d);
      setV({ tenant: "", listingId: "", amount: "", transactionId: "" });
      setOpen(false);
    } catch (err) {
      if (err instanceof ApiError && err.field) setErrors({ [err.field]: err.message });
      else setFormError(err instanceof Error ? err.message : "Couldn't create the receipt.");
    } finally {
      setBusy(false);
    }
  }
  if (!open) {
    return <button type="button" onClick={() => setOpen(true)} className="rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep">+ Generate deposit receipt</button>;
  }
  const field = (k: keyof typeof v, label: string, hint: string, extra: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium">{label}</span>
      <input value={v[k]} onChange={set(k)} {...extra} aria-invalid={!!errors[k]}
        className={`rounded-lg border bg-surface px-3 py-2 ${errors[k] ? "border-claim" : "border-line"}`} />
      <span className={`text-xs ${errors[k] ? "text-claim" : "text-muted"}`}>{errors[k] ?? hint}</span>
    </label>
  );
  return (
    <form onSubmit={submit} noValidate className="flex w-full flex-col gap-4 rounded-2xl border border-vault/30 bg-surface p-5">
      <div>
        <h2 className="text-lg">Generate a deposit receipt</h2>
        <p className="text-sm text-muted">For a deposit paid outside the app (bank transfer, UPI or cheque). TrustRent fingerprints the details and writes the receipt to the chain, the same as an in-app payment. The tenant and owner see it under Deposits.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {field("tenant", "Tenant", "Username, user ID or email of the person renting", { placeholder: "e.g. ranav2003" })}
        {field("listingId", "Home ID", "The ID shown on the listing", { placeholder: "e.g. IND-VN-101" })}
        {field("amount", "Deposit amount (₹)", "Whole rupees", { inputMode: "numeric", placeholder: "e.g. 34000" })}
        {field("transactionId", "Transaction ID", "Bank, UPI or cheque reference. Each can be used once.", { placeholder: "e.g. UPI 418022339170" })}
      </div>
      {formError && <p role="alert" className="text-sm text-claim">{formError}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep">{busy ? "Writing to the chain..." : "Generate receipt"}</button>
        <button type="button" onClick={() => { setOpen(false); setErrors({}); setFormError(null); }} className="rounded-lg px-3 py-2 text-sm text-muted hover:text-ink">Cancel</button>
      </div>
    </form>
  );
}
function Chain({ blocks, genesis, intact, network }: { blocks: LedgerBlock[]; genesis: string; intact: boolean; network: string }) {
  return (
    <section className="flex flex-col gap-3 self-start rounded-2xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg">The receipt chain</h2>
        <span className="flex items-center gap-2 text-sm">
          <Pill tone={intact ? "green" : "red"}>{intact ? "Every link checks out" : "Chain broken"}</Pill>
          <span className="text-muted">{networkLabel(network)}</span>
        </span>
      </div>
      <ol className="flex flex-col">
        <li className="flex items-center gap-3 text-xs text-muted"><span className="h-3 w-3 rounded-full border-2 border-muted" />Genesis {short(genesis)}</li>
        {blocks.map((b) => (
          <li key={b.seq} className="relative ml-1.5 border-l-2 border-vault/40 pt-3 pl-5">
            <span className="absolute top-6 -left-1.75 h-3 w-3 rounded-full bg-vault" />
            <div className="flex flex-col gap-1 rounded-xl border border-line p-3 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="font-medium">Block #{b.seq}, {b.kind === "deposit" ? "Deposit recorded" : "Settlement recorded"}, {b.depositId}</span>
                <span className="text-muted">{when(b.at, true)}</span>
              </div>
              <span className="text-muted">
                {b.kind === "deposit" ? `Amount ${formatINR(b.amounts.amount ?? 0)}` : `Deducted ${formatINR(b.amounts.deducted ?? 0)}, refunded ${formatINR(b.amounts.refunded ?? 0)}`}
              </span>
              <span className="grid gap-x-3 gap-y-0.5 sm:grid-cols-[110px_minmax(0,1fr)]">
                <span className="text-muted">Previous block</span><code className="break-all">{b.prevHash}</code>
                <span className="text-muted">Details hash</span><code className="break-all">{b.dataHash}</code>
                <span className="text-muted">This block</span><code className="break-all font-semibold text-vault">{b.hash}</code>
                {b.chainTx && (<><span className="text-muted">Polygon tx</span><code className="break-all">{b.chainTx}</code></>)}
              </span>
            </div>
          </li>
        ))}
      </ol>
      {!blocks.length && <p className="text-sm text-muted">No receipts yet.</p>}
    </section>
  );
}
export default function AdminDepositsPage() { // admin deposits
  const [deposits, setDeposits] = useState<Deposit[] | null>(null);
  const [ledger, setLedger] = useState<Awaited<ReturnType<typeof getLedger>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => {
    adminDeposits().then(setDeposits, (e) => setError(e.message));
    getLedger().then(setLedger, (e) => setError(e.message));
  }, []);
  useEffect(() => { reload(); }, [reload]);
  const [fresh, setFresh] = useState<string | null>(null);
  const added = (nd: Deposit) => {
    setDeposits((l) => [nd, ...(l ?? [])]);
    setFresh(nd.id);
    getLedger().then(setLedger);
    setTimeout(() => document.getElementById(nd.id)?.scrollIntoView({ behavior: "smooth", block: "center" }), 100);
  };
  const update = (nd: Deposit) => { setDeposits((l) => l!.map((x) => (x.id === nd.id ? nd : x))); getLedger().then(setLedger); };
  const held = deposits?.filter((d) => d.status !== "settled") ?? [];
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Deposits & receipts" intro="Every deposit gets a tamper-proof receipt. Settle disputes here; each decision is added to the chain as a new block.">
        <Link href="/deposits/lookup" className="rounded-lg border border-line bg-surface px-4 py-2 text-sm hover:border-ink/40">Look up a receipt</Link>
      </PageHeader>
      <GenerateReceipt onDone={added} />
      <section aria-label="How it works" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {STEPS.map((s, i) => (
          <div key={s.t} className="flex flex-col gap-1 rounded-xl border border-line bg-surface p-4">
            <span className="grid h-7 w-7 place-items-center rounded-full bg-vault text-xs font-semibold text-white">{i + 1}</span>
            <span className="font-medium">{s.t}</span>
            <span className="text-sm text-muted">{s.d}</span>
          </div>
        ))}
      </section>
      {!deposits ? <Loading error={error} /> : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Deposits" value={deposits.length} />
            <Stat label="Held now" value={formatINR(held.reduce((a, d) => a + d.amount, 0))} note={`${held.length} open`} />
            <Stat label="Disputed" value={deposits.filter((d) => d.status === "disputed").length} tone="warn" />
            <Stat label="Receipts verified" value={`${deposits.filter((d) => d.verification?.verified).length}/${deposits.length}`} tone="good" />
          </div>
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <section className="flex flex-col gap-4">
              <h2 className="text-lg">Deposits</h2>
              {deposits.length === 0 && <p className="text-sm text-muted">No deposits yet.</p>}
              {deposits.map((d) => (
                <div key={d.id} className="flex flex-col gap-2">
                  <DepositCard d={d} onChange={update} highlight={d.id === fresh} />
                  {d.status !== "settled" && <SettleForm d={d} onDone={update} />}
                  {d.ownerPayout === "due" && (
                    <button type="button" onClick={() => markOwnerPaid(d.id).then(update, (e) => setError(e.message))}
                      className="w-fit rounded-lg border border-line bg-surface px-3 py-1.5 text-sm hover:border-ink/40">Mark {formatINR(d.deducted ?? 0)} paid to owner</button>
                  )}
                </div>
              ))}
            </section>
            {ledger && <Chain {...ledger} />}
          </div>
        </>
      )}
      {error && deposits && <p role="alert" className="text-sm text-claim">{error}</p>}
    </div>
  );
}
