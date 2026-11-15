"use client";
import { FormEvent, useState } from "react";
import { REPORT_REASONS, reportListing } from "@/lib/trust";

export function ReportListing({ listingId }: { listingId: string }) { // report a home
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [details, setDetails] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!reason) return setError("Choose a reason.");
    setError(null);
    try {
      setDone((await reportListing(listingId, reason, details)).message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send the report.");
    }
  }
  if (done) return <p className="text-sm text-vault" role="status">{done}</p>;
  if (!open) return <button type="button" onClick={() => setOpen(true)} className="w-fit text-sm text-muted underline-offset-2 hover:text-claim hover:underline">Report this home</button>;
  return (
    <form onSubmit={submit} className="flex flex-col gap-2 rounded-xl border border-line bg-surface p-4 text-sm">
      <p className="font-medium">What&apos;s wrong with this home?</p>
      {Object.entries(REPORT_REASONS).map(([k, v]) => (
        <label key={k} className="flex items-center gap-2">
          <input type="radio" name="reason" value={k} checked={reason === k} onChange={() => setReason(k)} className="accent-vault" />{v}
        </label>
      ))}
      <textarea value={details} onChange={(e) => setDetails(e.target.value)} maxLength={1000} rows={2}
        placeholder="Anything that helps us check (optional, needed for “Something else”)" className="rounded-lg border border-line px-3 py-2" />
      <p className="text-xs text-muted">Never pay a deposit or token amount outside TrustRent. The owner doesn&apos;t see who reported.</p>
      {error && <p role="alert" className="text-claim">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" className="rounded-lg bg-claim px-4 py-2 font-medium text-white hover:opacity-90">Send report</button>
        <button type="button" onClick={() => setOpen(false)} className="px-3 text-muted hover:text-ink">Cancel</button>
      </div>
    </form>
  );
}
