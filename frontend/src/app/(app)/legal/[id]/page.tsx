"use client";
import Link from "next/link";
import { FormEvent, use, useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import {
  AgreementDoc, CaseDetail, Contact, downloadAgreement, fileSize, getCase, getContacts, markCaseRead,
  sendCaseMessage, shareAgreement, uploadAgreement,
} from "@/lib/legal";

const time = (iso: string) => new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

function Upload({ caseId, onDone }: { caseId: string; onDone: (c: CaseDetail) => void }) {
  const [title, setTitle] = useState("Rental agreement");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!file) return setError("Choose the PDF.");
    if (file.type && file.type !== "application/pdf") return setError("Upload the agreement as a PDF file.");
    setBusy(true);
    try {
      onDone(await uploadAgreement(caseId, title.trim(), file));
      setFile(null);
      if (input.current) input.current.value = "";
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't upload. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4">
      <p className="text-sm font-medium">Upload the agreement (PDF, up to 15 MB)</p>
      <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} aria-label="Document title"
        className="rounded-lg border border-line px-3 py-2 text-sm" />
      <input ref={input} type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} aria-label="Agreement PDF"
        className="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-vault-soft file:px-2 file:py-1 file:text-vault" />
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
      <button type="submit" disabled={busy} className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">
        {busy ? "Uploading..." : "Upload and send to owner"}
      </button>
    </form>
  );
}

function Share({ doc, contacts, onDone }: { doc: AgreementDoc; contacts: Contact[]; onDone: (c: CaseDetail) => void }) {
  const [tenant, setTenant] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const already = new Set((doc.sharedWith ?? []).map((s) => s.id));
  const options = contacts.filter((c) => !already.has(c.id));
  if (!contacts.length) {
    return <p className="text-xs text-muted">To share it, the tenant needs to have messaged you about a home or paid you a deposit on TrustRent.</p>;
  }
  if (!options.length) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap gap-2">
        <select value={tenant} onChange={(e) => setTenant(e.target.value)} aria-label="Share with tenant"
          className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-2 py-1.5 text-sm">
          <option value="">Share with a tenant...</option>
          {options.map((c) => <option key={c.id} value={c.id}>{c.name} (@{c.username}) · {c.via}</option>)}
        </select>
        <button type="button" disabled={!tenant || busy}
          onClick={() => { setBusy(true); setError(null); shareAgreement(doc.id, tenant).then((c) => { setTenant(""); onDone(c); }, (e) => setError(e.message)).finally(() => setBusy(false)); }}
          className="rounded-lg border border-vault px-3 py-1.5 text-sm text-vault hover:bg-vault-soft disabled:opacity-50">
          {busy ? "Sharing..." : "Share"}
        </button>
      </div>
      {error && <p role="alert" className="text-xs text-claim">{error}</p>}
    </div>
  );
}

export default function CasePage({ params }: { params: Promise<{ id: string }> }) { // legal case
  const { id } = use(params);
  const { user } = useAuth();
  const [c, setC] = useState<CaseDetail | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [dlError, setDlError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const count = c?.messages.length ?? 0;
  const load = useCallback(() => getCase(id).then(setC, (e) => setError(e.message)), [id]);
  useEffect(() => {
    load();
    const t = window.setInterval(() => { if (document.visibilityState === "visible") load(); }, 5000);
    return () => window.clearInterval(t);
  }, [load]);
  useEffect(() => {
    if (c && c.side !== "admin") markCaseRead(id).catch(() => {});
  }, [id, count, c?.side]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (c?.side === "owner") getContacts().then(setContacts, () => {});
  }, [c?.side]);
  useEffect(() => { bottom.current?.scrollIntoView({ block: "nearest" }); }, [count]);
  if (!user) return null;
  if (!c) return <p className="text-sm text-muted" role={error ? "alert" : "status"}>{error ?? "Loading..."}</p>;
  const back = c.side === "lawyer" ? "/lawyer" : c.side === "owner" ? "/owner/lawyers" : "/admin/legal";
  const other = c.side === "lawyer" ? c.owner.name : c.lawyer.name;
  const canWrite = c.side !== "admin" && (c.side === "lawyer" || c.lawyer.available);
  async function send(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSending(true);
    setError(null);
    try {
      setC(await sendCaseMessage(id, text.trim()));
      setText("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't send. Try again.");
    } finally {
      setSending(false);
    }
  }
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href={back} className="text-sm text-vault hover:underline">← Back</Link>
        <h1 className="mt-2 text-2xl sm:text-3xl">{c.subject}</h1>
        <p className="mt-1 text-sm text-muted">
          {c.side === "admin" ? `${c.owner.name} with ${c.lawyer.name}` : `With ${other}`}
          {c.listing && <> · <span>{c.listing.area}</span></>}
          {c.side === "lawyer" && c.owner.phone && <> · {c.owner.phone} · {c.owner.email}</>}
        </p>
        {!c.lawyer.available && c.side !== "lawyer" && (
          <p role="status" className="mt-3 rounded-lg bg-amber-soft px-3 py-2 text-sm text-amber">This lawyer is no longer available on TrustRent. You can still download the documents below.</p>
        )}
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section className="flex flex-col gap-3" aria-label="Messages">
          <ol className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto rounded-2xl border border-line bg-surface p-4">
            {c.messages.map((m) => {
              const mine = m.senderId === user.id;
              return (
                <li key={m.id} className={`flex max-w-[85%] flex-col gap-0.5 ${mine ? "self-end items-end" : "self-start"}`}>
                  <span className={`rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap ${mine ? "bg-vault text-white" : "bg-mist"}`}>{m.text}</span>
                  <span className="text-[11px] text-muted">{mine ? "You" : m.senderName} · {time(m.createdAt)}</span>
                </li>
              );
            })}
            <div ref={bottom} />
          </ol>
          {canWrite && (
            <form onSubmit={send} className="flex gap-2">
              <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} maxLength={2000} aria-label="Message"
                placeholder={c.side === "owner" ? "Share the tenant's name, rent, deposit and dates..." : "Write to the owner..."}
                className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-sm" />
              <button type="submit" disabled={sending || !text.trim()} className="self-end rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
                {sending ? "..." : "Send"}
              </button>
            </form>
          )}
          {error && <p role="alert" className="text-sm text-claim">{error}</p>}
        </section>
        <section className="flex flex-col gap-3" aria-label="Documents">
          <h2 className="text-lg">Documents</h2>
          {c.side === "lawyer" && <Upload caseId={c.id} onDone={setC} />}
          {!c.documents.length ? (
            <p className="text-sm text-muted">{c.side === "lawyer" ? "Nothing uploaded yet." : "The lawyer hasn't shared a document yet."}</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {c.documents.map((d) => (
                <li key={d.id} className="flex flex-col gap-2 rounded-xl border border-line bg-surface p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium">{d.title}</p>
                      <p className="truncate text-xs text-muted">{d.fileName} · {fileSize(d.size)} · {time(d.createdAt)}</p>
                    </div>
                    <button type="button" onClick={() => { setDlError(null); downloadAgreement(d).catch((e) => setDlError(e.message)); }}
                      className="shrink-0 rounded-lg bg-vault px-3 py-1.5 text-sm font-medium text-white hover:bg-vault-deep">Download</button>
                  </div>
                  <p className="text-[11px] break-all text-muted" title="SHA-256 fingerprint: if the file changes, this changes">Fingerprint {d.fileHash}</p>
                  {!!d.sharedWith?.length && <p className="text-xs">Shared with {d.sharedWith.map((s) => s.name).join(", ")}</p>}
                  {c.side === "owner" && <Share doc={d} contacts={contacts} onDone={setC} />}
                </li>
              ))}
            </ul>
          )}
          {dlError && <p role="alert" className="text-sm text-claim">{dlError}</p>}
          {c.side === "owner" && c.documents.length > 0 && (
            <p className="text-xs text-muted">Print the agreement and sign it with the tenant. Rental agreements need stamp duty, and those of 11 months or more must be registered: your lawyer will guide you.</p>
          )}
        </section>
      </div>
    </div>
  );
}
