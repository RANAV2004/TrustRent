"use client";
import { FormEvent, useEffect, useState } from "react";
import { agreementDocumentUrl, AgreementTerms, AgreementView, Deposit, getAgreement, saveAgreement, signAgreement } from "@/lib/deposits";

const when = (iso: string) => new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
const STATUS = { draft: "Waiting for signatures", partly_signed: "Signed by one side", signed: "Signed by both" };

function TermsForm({ d, initial, onSaved }: { d: Deposit; initial?: AgreementTerms; onSaved: (v: AgreementView) => void }) {
  const [t, setT] = useState<AgreementTerms>(initial ?? {
    startDate: new Date().toISOString().slice(0, 10), months: 11, monthlyRent: 0, rentDueDay: 5, noticeDays: 30, lockInMonths: 0,
    maintenance: "", extraClauses: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const num = (k: keyof AgreementTerms) => (e: { target: { value: string } }) => setT({ ...t, [k]: Number(e.target.value.replace(/\D/g, "")) || 0 });
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSaved(await saveAgreement(d.id, t));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the agreement.");
    } finally {
      setBusy(false);
    }
  }
  const field = "rounded-lg border border-line bg-surface px-3 py-2";
  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm"><span className="text-xs text-muted">Start date</span>
          <input type="date" value={t.startDate} onChange={(e) => setT({ ...t, startDate: e.target.value })} className={field} /></label>
        <label className="flex flex-col gap-1 text-sm"><span className="text-xs text-muted">Months</span>
          <input inputMode="numeric" value={t.months || ""} onChange={num("months")} className={field} /></label>
        <label className="flex flex-col gap-1 text-sm"><span className="text-xs text-muted">Monthly rent (₹)</span>
          <input inputMode="numeric" value={t.monthlyRent || ""} onChange={num("monthlyRent")} className={field} /></label>
        <label className="flex flex-col gap-1 text-sm"><span className="text-xs text-muted">Rent due by day</span>
          <input inputMode="numeric" value={t.rentDueDay || ""} onChange={num("rentDueDay")} className={field} /></label>
        <label className="flex flex-col gap-1 text-sm"><span className="text-xs text-muted">Notice period (days)</span>
          <input inputMode="numeric" value={t.noticeDays} onChange={num("noticeDays")} className={field} /></label>
        <label className="flex flex-col gap-1 text-sm"><span className="text-xs text-muted">Lock-in (months)</span>
          <input inputMode="numeric" value={t.lockInMonths} onChange={num("lockInMonths")} className={field} /></label>
      </div>
      <label className="flex flex-col gap-1 text-sm"><span className="text-xs text-muted">Maintenance and utilities</span>
        <input value={t.maintenance} maxLength={200} onChange={(e) => setT({ ...t, maintenance: e.target.value })} placeholder="e.g. Tenant pays electricity; society maintenance included in rent" className={field} /></label>
      <label className="flex flex-col gap-1 text-sm"><span className="text-xs text-muted">Other terms (optional)</span>
        <textarea value={t.extraClauses} maxLength={4000} rows={3} onChange={(e) => setT({ ...t, extraClauses: e.target.value })} className={field} /></label>
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
      <button type="submit" disabled={busy} className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">
        {busy ? "Saving..." : "Save agreement and ask the tenant to sign"}
      </button>
    </form>
  );
}

export function AgreementPanel({ d }: { d: Deposit }) { // rent agreement
  const [view, setView] = useState<AgreementView | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getAgreement(d.id).then(setView, () => setView(null));
  }, [d.id]);
  if (!view || (!view.agreement && !view.canCreate)) return null;
  const a = view.agreement;
  async function sign(e: FormEvent) {
    e.preventDefault();
    if (!agree) return setError("Tick the box to confirm you agree to every term.");
    setBusy(true);
    setError(null);
    try {
      setView(await signAgreement(d.id, name));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign.");
    } finally {
      setBusy(false);
    }
  }
  async function print() {
    try {
      window.open(await agreementDocumentUrl(d.id), "_blank", "noopener");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open the agreement.");
    }
  }
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-line p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-medium">Rent agreement</h3>
        {a && <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${a.status === "signed" ? "bg-vault-soft text-vault" : "bg-amber-soft text-amber"}`}>{STATUS[a.status]}</span>}
      </div>
      {!a || editing ? (
        <>
          <p className="text-sm text-muted">Draft the rent agreement. Once someone signs, it can&apos;t be changed.</p>
          <TermsForm d={d} initial={a?.terms} onSaved={(v) => { setView(v); setEditing(false); }} />
        </>
      ) : (
        <>
          <button type="button" onClick={() => setOpen((o) => !o)} className="w-fit text-sm text-vault hover:underline">{open ? "Hide the agreement" : "Read the agreement"}</button>
          {open && <div className="max-h-80 overflow-y-auto rounded-lg bg-mist p-4 text-sm whitespace-pre-line">{a.text}</div>}
          <ul className="text-sm">
            {a.signatures.map((s) => <li key={s.role}><span className="capitalize">{s.role}</span>: <strong>{s.typedName}</strong>, {when(s.signedAt)}</li>)}
          </ul>
          <p className={`text-xs ${a.verified ? "text-vault" : "text-claim"}`}>
            {a.verified ? "The text matches its fingerprint and every signature covers this exact text." : "Warning: the text no longer matches what was signed. Contact TrustRent."}
          </p>
          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={print} className="text-sm text-vault hover:underline">Open printable copy</button>
            {view.canCreate && <button type="button" onClick={() => setEditing(true)} className="text-sm text-vault hover:underline">Edit terms</button>}
          </div>
          {view.canSign && (
            <form onSubmit={sign} className="flex flex-col gap-2 rounded-lg bg-mist p-3">
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-xs text-muted">Type your full name to sign: {view.signAs}</span>
                <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" className="rounded-lg border border-line bg-surface px-3 py-2" />
              </label>
              <label className="flex items-start gap-2 text-sm">
                <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-1 h-4 w-4 accent-vault" />
                I have read the whole agreement and agree to every term.
              </label>
              <button type="submit" disabled={busy} className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">Sign agreement</button>
            </form>
          )}
        </>
      )}
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
    </section>
  );
}
