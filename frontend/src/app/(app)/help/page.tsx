"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ImagePicker, StatusPill } from "@/components/support-ui";
import { ApiError, apiMode } from "@/lib/api";
import { CATEGORIES, getTicket, MAX_IMAGE_MB, myTickets, raiseTicket, TicketSummary, when } from "@/lib/support";

function FindTicket() {
  const router = useRouter();
  const [no, setNo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function find(e: FormEvent) {
    e.preventDefault();
    if (!no.trim()) return;
    setError(null);
    setBusy(true);
    try {
      const t = await getTicket(no);
      router.push(`/help/${t.ticketNo}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't search right now. Try again.");
      setBusy(false);
    }
  }
  return (
    <form onSubmit={find} className="flex flex-col gap-2 rounded-2xl border border-line bg-surface p-5">
      <label htmlFor="find" className="font-medium">Find a ticket</label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input id="find" value={no} onChange={(e) => setNo(e.target.value)} placeholder="TKT-261126-4F7K" autoComplete="off"
          className="min-w-0 flex-1 rounded-lg border border-line px-3 py-2 font-mono uppercase placeholder:normal-case" />
        <button type="submit" disabled={busy || !no.trim()} className="rounded-lg border border-vault px-4 py-2 text-sm font-medium text-vault hover:bg-vault-soft disabled:opacity-50">
          {busy ? "Searching..." : "Search"}
        </button>
      </div>
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
    </form>
  );
}

function RaiseQuery({ onRaised }: { onRaised: (ticketNo: string) => void }) {
  const [category, setCategory] = useState("");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fix = (field: string) => setErrors((all) => { const next = { ...all }; delete next[field]; return next; });
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const found: Record<string, string> = {};
    if (!category) found.category = "Choose what your query is about.";
    if (subject.trim().length < 5) found.subject = "Give your query a short title (at least 5 characters).";
    if (description.trim().length < 20) found.description = "Describe the problem in at least 20 characters.";
    if (files.some((f) => f.size > MAX_IMAGE_MB * 1024 * 1024)) found.images = `Each screenshot must be under ${MAX_IMAGE_MB} MB.`;
    setErrors(found);
    if (Object.keys(found).length) return;
    const form = new FormData();
    form.append("category", category);
    form.append("subject", subject.trim());
    form.append("description", description.trim());
    const from = document.referrer ? new URL(document.referrer) : null;
    form.append("pageUrl", from && from.origin === window.location.origin ? from.pathname : "");
    files.forEach((f) => form.append("images", f));
    setBusy(true);
    try {
      const t = await raiseTicket(form);
      onRaised(t.ticketNo);
    } catch (err) {
      if (err instanceof ApiError && err.field) setErrors({ [err.field]: err.message });
      else setError(err instanceof ApiError ? err.message : "Couldn't send your query. Try again.");
      setBusy(false);
    }
  }
  const field = "w-full rounded-lg border bg-surface px-3 py-2.5 text-[15px]";
  return (
    <form onSubmit={submit} className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-5" noValidate>
      <h2 className="text-lg">Raise a query</h2>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="category" className="text-sm font-medium">What is it about?</label>
        <select id="category" value={category} onChange={(e) => { setCategory(e.target.value); fix("category"); }} className={`${field} ${errors.category ? "border-claim" : "border-line"}`}>
          <option value="">Choose...</option>
          {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </select>
        {errors.category && <span className="text-xs text-claim">{errors.category}</span>}
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="subject" className="text-sm font-medium">Problem</label>
        <input id="subject" value={subject} onChange={(e) => { setSubject(e.target.value); fix("subject"); }} maxLength={120}
          placeholder="e.g. Payment taken but Premium not active" className={`${field} ${errors.subject ? "border-claim" : "border-line"}`} />
        {errors.subject && <span className="text-xs text-claim">{errors.subject}</span>}
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="description" className="text-sm font-medium">Description</label>
        <textarea id="description" value={description} onChange={(e) => { setDescription(e.target.value); fix("description"); }} rows={5} maxLength={4000}
          placeholder="What happened, what you expected, and any reference numbers (deposit ID, payment ID)."
          className={`${field} ${errors.description ? "border-claim" : "border-line"}`} />
        <span className={`text-xs ${errors.description ? "text-claim" : "text-muted"}`}>{errors.description ?? `${description.length}/4000. Never share your password or codes.`}</span>
      </div>
      <ImagePicker files={files} onChange={(f) => { setFiles(f); fix("images"); }} />
      {errors.images && <p className="text-xs text-claim">{errors.images}</p>}
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
      <button type="submit" disabled={busy} className="w-fit rounded-lg bg-vault px-5 py-2.5 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">
        {busy ? "Sending..." : "Submit query"}
      </button>
    </form>
  );
}

export default function HelpPage() {
  const [tickets, setTickets] = useState<TicketSummary[] | null>(null);
  const [raised, setRaised] = useState<string | null>(null);
  const [formKey, setFormKey] = useState(0);
  useEffect(() => { if (apiMode) myTickets().then(setTickets, () => setTickets([])); }, [raised]);
  if (!apiMode) return <p className="text-sm text-muted">Help & support needs the TrustRent server. It isn&apos;t available in this demo.</p>;
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl">Help & support</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">Tell us what went wrong and we&apos;ll get back to you, usually within one working day. Every query gets a ticket number you can use to follow it.</p>
      </div>
      {raised && (
        <div role="status" className="flex flex-col gap-2 rounded-2xl border border-vault/30 bg-vault-soft p-5">
          <p className="text-vault">Your query was sent. Your ticket number is</p>
          <p className="font-mono text-2xl font-semibold tracking-wide text-vault">{raised}</p>
          <p className="text-sm text-muted">We&apos;ve emailed it to you too. Use it to check progress below or on the ticket page.</p>
          <div className="flex gap-3">
            <Link href={`/help/${raised}`} className="rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white">View ticket</Link>
            <button type="button" onClick={() => { setRaised(null); setFormKey((k) => k + 1); }} className="text-sm text-vault hover:underline">Raise another query</button>
          </div>
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex flex-col gap-6">
          {!raised && <RaiseQuery key={formKey} onRaised={(no) => { setRaised(no); window.scrollTo({ top: 0 }); }} />}
        </div>
        <div className="flex flex-col gap-6">
          <FindTicket />
          <section className="flex flex-col gap-3">
            <h2 className="text-lg">My queries</h2>
            {!tickets ? <p className="text-sm text-muted">Loading...</p> : !tickets.length ? (
              <p className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">You haven&apos;t raised any queries.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {tickets.map((t) => (
                  <li key={t.ticketNo}>
                    <Link href={`/help/${t.ticketNo}`} className="flex flex-col gap-1 rounded-xl border border-line bg-surface px-4 py-3 hover:border-ink/30">
                      <span className="flex items-center justify-between gap-2">
                        <span className="font-mono text-sm font-medium">{t.ticketNo}</span>
                        <StatusPill status={t.status} label={t.statusLabel} />
                      </span>
                      <span className="truncate text-sm">{t.subject}</span>
                      <span className="text-xs text-muted">{t.category} · updated {when(t.updatedAt)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
