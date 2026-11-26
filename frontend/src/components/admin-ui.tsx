"use client";
import { ReactNode, useState } from "react";
export const when = (iso: string | null | undefined, withTime = false) =>
  iso ? new Date(iso).toLocaleString("en-IN", withTime
    ? { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }
    : { day: "numeric", month: "short", year: "numeric" }) : "NA";
export function PageHeader({ title, intro, children }: { title: string; intro?: string; children?: ReactNode }) { // page header
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl sm:text-3xl">{title}</h1>
        {intro && <p className="mt-1 max-w-2xl text-sm text-muted">{intro}</p>}
      </div>
      {children}
    </div>
  );
}
export function Stat({ label, value, note, tone }: { label: string; value: ReactNode; note?: string; tone?: "warn" | "good" }) { // stat
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-line bg-surface p-4">
      <span className="text-xs tracking-wide text-muted uppercase">{label}</span>
      <span className={`font-display text-2xl font-semibold tabular ${tone === "warn" ? "text-amber" : tone === "good" ? "text-vault" : ""}`}>{value}</span>
      {note && <span className="text-xs text-muted">{note}</span>}
    </div>
  );
}
const PILL = {
  green: "bg-vault-soft text-vault", amber: "bg-amber-soft text-amber", red: "bg-claim-soft text-claim",
  grey: "bg-mist text-muted", dark: "bg-ink text-white",
};
export function Pill({ tone, children }: { tone: keyof typeof PILL; children: ReactNode }) { // pill
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${PILL[tone]}`}>{children}</span>;
}
export function ConfirmAction({ label, confirmLabel, danger = false, reasonPlaceholder, onConfirm }: { // confirm action
  label: string; confirmLabel: string; danger?: boolean; reasonPlaceholder?: string;
  onConfirm: (reason: string) => Promise<unknown>;
}) {
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = danger ? "border-claim/40 text-claim hover:bg-claim-soft" : "border-line hover:border-ink/40";
  if (!asking) {
    return <button type="button" onClick={() => setAsking(true)} className={`rounded-md border px-2.5 py-1 text-xs ${base}`}>{label}</button>;
  }
  return (
    <span className="flex flex-col gap-1.5">
      <span className="flex flex-wrap items-center gap-1.5">
        {reasonPlaceholder && (
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={reasonPlaceholder} aria-label={reasonPlaceholder}
            className="w-44 rounded-md border border-line px-2 py-1 text-xs" />
        )}
        <button type="button" disabled={busy}
          onClick={() => { setBusy(true); setError(null); onConfirm(reason).catch((e) => setError(e.message)).finally(() => setBusy(false)); }}
          className={`rounded-md px-2.5 py-1 text-xs font-medium text-white ${danger ? "bg-claim" : "bg-vault"}`}>
          {busy ? "Working..." : confirmLabel}
        </button>
        <button type="button" onClick={() => { setAsking(false); setError(null); }} className="px-1 text-xs text-muted">Cancel</button>
      </span>
      {error && <span role="alert" className="text-xs text-claim">{error}</span>}
    </span>
  );
}
export function Loading({ error }: { error?: string | null }) { // loading
  return error ? <p role="alert" className="text-sm text-claim">{error}</p> : <p className="text-sm text-muted">Loading...</p>;
}
export function Search({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) { // search
  return (
    <input type="search" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label={placeholder}
      className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm sm:w-72" />
  );
}
