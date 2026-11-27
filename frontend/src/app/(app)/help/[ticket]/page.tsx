"use client";
import Link from "next/link";
import { FormEvent, use, useCallback, useEffect, useState } from "react";
import { ImagePicker, Screenshots, StatusPill } from "@/components/support-ui";
import { ApiError } from "@/lib/api";
import { getTicket, replyToTicket, setTicketStatus, Ticket, TicketStatus, when } from "@/lib/support";

function SupportActions({ t, onChange }: { t: Ticket; onChange: (t: Ticket) => void }) {
  const [closing, setClosing] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function go(status: TicketStatus, text = "") {
    setBusy(true);
    setError(null);
    try {
      onChange(await setTicketStatus(t.ticketNo, status, text));
      setClosing(false);
      setNote("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't update the ticket.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4">
      <h2 className="text-sm font-medium tracking-wide text-muted uppercase">Support actions</h2>
      {closing ? (
        <div className="flex flex-col gap-2">
          <label htmlFor="resolution" className="text-sm font-medium">How was it resolved? (the user sees this)</label>
          <textarea id="resolution" rows={3} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000}
            className="rounded-lg border border-line px-3 py-2 text-sm" />
          <div className="flex gap-2">
            <button type="button" disabled={busy || note.trim().length < 5} onClick={() => go("closed", note.trim())}
              className="rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy ? "Closing..." : "Close as resolved"}</button>
            <button type="button" onClick={() => setClosing(false)} className="px-2 text-sm text-muted">Cancel</button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {t.status === "open" && (
            <button type="button" disabled={busy} onClick={() => go("in_progress")} className="rounded-lg border border-line px-3 py-2 text-sm hover:border-ink/40">Mark in progress</button>
          )}
          {t.status !== "closed" ? (
            <button type="button" onClick={() => setClosing(true)} className="rounded-lg bg-vault px-3 py-2 text-sm font-medium text-white hover:bg-vault-deep">Resolve and close</button>
          ) : (
            <button type="button" disabled={busy} onClick={() => go("open", "Reopened by TrustRent support.")} className="rounded-lg border border-line px-3 py-2 text-sm hover:border-ink/40">Reopen</button>
          )}
        </div>
      )}
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
    </section>
  );
}

function Reply({ t, onSent }: { t: Ticket; onSent: (t: Ticket) => void }) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function send(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      onSent(await replyToTicket(t.ticketNo, text.trim(), files));
      setText("");
      setFiles([]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't send. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={send} className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4">
      <label htmlFor="reply" className="text-sm font-medium">{t.isSupport ? "Reply to the user" : "Add a message"}</label>
      <textarea id="reply" rows={3} maxLength={4000} value={text} onChange={(e) => setText(e.target.value)}
        placeholder={t.isSupport ? "The user gets this by email too." : "Add more details or answer our question."}
        className="rounded-lg border border-line px-3 py-2 text-sm" />
      <ImagePicker files={files} onChange={setFiles} id="reply-images" />
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
      <button type="submit" disabled={busy || !text.trim()} className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
        {busy ? "Sending..." : "Send"}
      </button>
    </form>
  );
}

export default function TicketPage({ params }: { params: Promise<{ ticket: string }> }) {
  const { ticket } = use(params);
  const [t, setT] = useState<Ticket | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => getTicket(decodeURIComponent(ticket)).then(setT, (e) => setError(e.message)), [ticket]);
  useEffect(() => {
    load();
    const id = window.setInterval(() => { if (document.visibilityState === "visible") load(); }, 30000);
    return () => window.clearInterval(id);
  }, [load]);
  if (!t) {
    return (
      <div className="flex flex-col gap-3">
        <Link href="/help" className="text-sm text-vault hover:underline">← Help & support</Link>
        <p role={error ? "alert" : "status"} className={`text-sm ${error ? "text-claim" : "text-muted"}`}>{error ?? "Loading..."}</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href={t.isSupport ? "/admin/queries" : "/help"} className="text-sm text-vault hover:underline">← {t.isSupport ? "Queries" : "Help & support"}</Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-2xl sm:text-3xl">{t.ticketNo}</h1>
          <StatusPill status={t.status} label={t.statusLabel} />
        </div>
        <p className="mt-1 text-sm text-muted">{t.category} · raised {when(t.createdAt)}{t.user ? ` by ${t.user.name} (${t.user.email}, ${t.user.accountType})` : ""}</p>
      </div>
      {t.status === "closed" && (
        <div className="rounded-2xl border border-vault/30 bg-vault-soft p-4 text-sm">
          <p className="font-medium text-vault">Resolved {when(t.closedAt)}</p>
          {t.resolution && <p className="mt-1">{t.resolution}</p>}
          {!t.isSupport && <p className="mt-2 text-muted">Still having trouble? <Link href="/help" className="text-vault hover:underline">Raise a new query</Link>.</p>}
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex flex-col gap-4">
          <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
            <h2 className="text-lg">{t.subject}</h2>
            <p className="text-sm whitespace-pre-wrap">{t.description}</p>
            {t.pageUrl && <p className="text-xs text-muted">Page: {t.pageUrl}</p>}
            <Screenshots ticketNo={t.ticketNo} images={t.images} />
          </section>
          <section aria-label="Progress" className="flex flex-col gap-3">
            <h2 className="text-lg">Progress</h2>
            <ol className="flex flex-col gap-3 border-l-2 border-line pl-4">
              <li className="text-sm"><span className="font-medium">Query raised</span> <span className="text-muted">· {when(t.createdAt)}</span></li>
              {t.timeline.map((e) => (
                <li key={e.id} className="flex flex-col gap-1.5 text-sm">
                  {e.kind === "status" ? (
                    <span><span className="font-medium">Status: {e.statusLabel}</span> <span className="text-muted">· {e.author} · {when(e.createdAt)}</span></span>
                  ) : (
                    <span><span className="font-medium">{e.fromSupport ? "TrustRent support" : e.author}</span> <span className="text-muted">· {when(e.createdAt)}</span></span>
                  )}
                  {e.text && <p className={`rounded-xl px-3 py-2 whitespace-pre-wrap ${e.fromSupport ? "bg-vault-soft" : "bg-mist"}`}>{e.text}</p>}
                  <Screenshots ticketNo={t.ticketNo} images={e.images} />
                </li>
              ))}
            </ol>
            {!t.timeline.length && <p className="text-sm text-muted">We haven&apos;t replied yet. You&apos;ll get an email when we do.</p>}
          </section>
        </div>
        <div className="flex flex-col gap-4">
          {t.isSupport && <SupportActions t={t} onChange={setT} />}
          {t.canReply ? <Reply t={t} onSent={setT} /> : (
            <p className="rounded-2xl border border-dashed border-line p-4 text-sm text-muted">This ticket is closed, so it can&apos;t take new messages.</p>
          )}
        </div>
      </div>
    </div>
  );
}
