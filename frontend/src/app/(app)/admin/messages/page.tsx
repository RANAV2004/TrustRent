"use client";
import { useEffect, useMemo, useState } from "react";
import { Loading, PageHeader, Search, when } from "@/components/admin-ui";
import { AdminConversation, AdminMessage, getConversationMessages, getConversations } from "@/lib/admin";
export default function AdminMessagesPage() { // admin chats
  const [convs, setConvs] = useState<AdminConversation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<AdminConversation | null>(null);
  const [msgs, setMsgs] = useState<AdminMessage[] | null>(null);
  useEffect(() => { getConversations().then(setConvs, (e) => setError(e.message)); }, []);
  function show(c: AdminConversation) {
    setOpen(c);
    setMsgs(null);
    getConversationMessages(c.id).then(setMsgs, (e) => setError(e.message));
  }
  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    return (convs ?? []).filter((c) => !t || [c.seeker.name, c.owner.name, c.listing.title, c.listing.id].some((v) => v.toLowerCase().includes(t)));
  }, [convs, q]);
  return (
    <div>
      <PageHeader title="Messages" intro="Read-only view of conversations between people looking for homes and owners, for safety checks and deposit disputes." />
      <div className="mb-4"><Search value={q} onChange={setQ} placeholder="Search by person or home" /></div>
      {!convs ? <Loading error={error} /> : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
          <ul className="flex flex-col overflow-hidden rounded-xl border border-line bg-surface">
            {shown.map((c) => (
              <li key={c.id} className="border-b border-line last:border-0">
                <button type="button" onClick={() => show(c)} aria-current={open?.id === c.id ? "true" : undefined}
                  className={`flex w-full flex-col gap-0.5 px-4 py-3 text-left text-sm ${open?.id === c.id ? "bg-vault-soft" : "hover:bg-mist/60"}`}>
                  <span className="flex justify-between gap-2"><span className="font-medium">{c.seeker.name} and {c.owner.name}</span><span className="shrink-0 text-xs text-muted">{when(c.updatedAt)}</span></span>
                  <span className="truncate text-xs text-muted">{c.listing.title}, {c.messages} message{c.messages === 1 ? "" : "s"}</span>
                  <span className="truncate text-xs">{c.last}</span>
                </button>
              </li>
            ))}
            {!shown.length && <li className="p-6 text-center text-sm text-muted">No conversations.</li>}
          </ul>
          <section className="flex min-h-80 flex-col rounded-xl border border-line bg-surface">
            {!open ? <p className="m-auto p-6 text-sm text-muted">Choose a conversation to read it.</p> : (
              <>
                <header className="border-b border-line px-4 py-3">
                  <p className="font-medium">{open.listing.title}</p>
                  <p className="text-xs text-muted">Looking: {open.seeker.name}, Owner: {open.owner.name}, read-only</p>
                </header>
                <ol className="flex flex-col gap-3 p-4">
                  {!msgs ? <li className="text-sm text-muted">Loading...</li> : msgs.map((m) => (
                    <li key={m.id} className={`flex max-w-[80%] flex-col gap-0.5 ${m.from === "owner" ? "self-end items-end" : "items-start"}`}>
                      <span className="text-xs text-muted">{m.senderName}, {m.from === "owner" ? "Owner" : "Looking for a home"}, {when(m.createdAt, true)}</span>
                      <span className={`rounded-2xl px-3 py-2 text-sm ${m.from === "owner" ? "bg-vault text-white" : "bg-mist"}`}>
                        {m.kind === "visit"
                          ? `Visit request (${m.visit?.status ?? "pending"})${m.visit?.acceptedSlot ? `: ${when(m.visit.acceptedSlot, true)}` : ""}${m.text ? `, ${m.text}` : ""}`
                          : m.text}
                      </span>
                    </li>
                  ))}
                </ol>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
