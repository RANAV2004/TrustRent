"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useStore } from "@/lib/local-store";
import {
  Conversation, conversationsFor, formatSlot, formatTime, getConversation, isUnread, lastMessage, markRead,
  Message, messagesIn, requestVisit, respondToVisit, sendText,
} from "@/lib/messages";
function VisitCard({ m, mine, canRespond, onRespond }: { m: Message; mine: boolean; canRespond: boolean; onRespond: (accept: boolean, slot?: string) => void }) {
  const v = m.visit!;
  const tone = v.status === "accepted" ? "border-vault/40 bg-vault-soft" : v.status === "declined" ? "border-claim/30 bg-claim-soft" : "border-line bg-surface";
  return (
    <div className={`flex w-full max-w-sm flex-col gap-2 rounded-2xl border p-4 ${tone} ${mine ? "self-end" : "self-start"}`}>
      <p className="text-sm font-semibold">
        {v.status === "accepted" ? "Visit confirmed" : v.status === "declined" ? "Visit declined" : "Visit request"}
      </p>
      {v.status === "accepted" && v.acceptedSlot ? (
        <p className="text-sm">{formatSlot(v.acceptedSlot)}</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {v.slots.map((s) => (
            <li key={s} className="flex items-center justify-between gap-2 text-sm">
              <span>{formatSlot(s)}</span>
              {canRespond && v.status === "pending" && (
                <button type="button" onClick={() => onRespond(true, s)} className="rounded-md bg-vault px-2.5 py-1 text-xs font-medium text-white hover:bg-vault-deep">Accept</button>
              )}
            </li>
          ))}
        </ul>
      )}
      {m.text && <p className="text-sm text-muted">&ldquo;{m.text}&rdquo;</p>}
      {canRespond && v.status === "pending" && (
        <button type="button" onClick={() => onRespond(false)} className="self-start text-xs text-claim hover:underline">None of these work</button>
      )}
      {!canRespond && v.status === "pending" && <p className="text-xs text-muted">Waiting for the owner to pick a time.</p>}
    </div>
  );
}
function Thread({ c }: { c: Conversation }) {
  const { user } = useAuth();
  const msgs = useStore(() => messagesIn(c.id), [c.id]);
  const [text, setText] = useState("");
  const [proposing, setProposing] = useState(false);
  const [slots, setSlots] = useState(["", ""]);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const isOwner = user?.id === c.ownerId;
  const other = isOwner ? c.seekerName : c.ownerName;
  useEffect(() => {
    if (user) markRead(c.id, user.id);
    bottom.current?.scrollIntoView({ block: "end" });
  }, [c.id, msgs.length, user]);
  if (!user) return null;
  async function guard(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send. Try again.");
    }
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (proposing) {
      const chosen = slots.filter(Boolean);
      if (!chosen.length) return setError("Pick at least one time.");
      if (chosen.some((s) => new Date(s).getTime() < Date.now())) return setError("Times must be in the future.");
      const note = text;
      setProposing(false);
      setSlots(["", ""]);
      setText("");
      guard(() => requestVisit(c, user!, chosen.map((s) => new Date(s).toISOString()), note));
      return;
    }
    if (!text.trim()) return;
    const body = text;
    setText("");
    guard(() => sendText(c, user!, body));
  }
  return (
    <div className="flex h-full min-h-[560px] flex-col">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3">
        <div className="min-w-0">
          <p className="truncate font-semibold">{other}</p>
          <p className="truncate text-sm text-muted">
            {isOwner ? "Interested in" : "Owner of"} <Link href={`/listings/${c.listingId}`} className="text-vault hover:underline">{c.listingTitle}</Link>, {c.listingArea}
          </p>
        </div>
        <Link href="/messages" className="text-sm text-muted hover:text-ink md:hidden">All chats</Link>
      </header>
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-5 py-4" aria-live="polite">
        {msgs.length === 0 && <p className="text-center text-sm text-muted">Say hello and ask anything about the home.</p>}
        {msgs.map((m) => {
          const mine = m.senderId === user.id;
          if (m.kind === "visit") {
            return (
              <VisitCard key={m.id} m={m} mine={mine} canRespond={isOwner && !mine}
                onRespond={(accept, slot) => guard(() => respondToVisit(m.id, user, accept, slot))} />
            );
          }
          return (
            <div key={m.id} className={`flex max-w-[80%] flex-col gap-0.5 ${mine ? "self-end items-end" : "self-start items-start"}`}>
              <p className={`rounded-2xl px-3.5 py-2 text-[15px] whitespace-pre-line ${mine ? "rounded-br-md bg-vault text-white" : "rounded-bl-md bg-mist"}`}>{m.text}</p>
              <span className="text-[11px] text-muted">{formatTime(m.createdAt)}</span>
            </div>
          );
        })}
        <div ref={bottom} />
      </div>
      <form onSubmit={submit} className="flex flex-col gap-2 border-t border-line p-3">
        {proposing && (
          <div className="flex flex-col gap-2 rounded-xl bg-mist p-3">
            <p className="text-sm font-medium">Suggest times to see the home</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {slots.map((s, i) => (
                <label key={i} className="flex flex-col gap-1 text-xs text-muted">
                  Option {i + 1}
                  <input type="datetime-local" value={s} onChange={(e) => setSlots(slots.map((x, j) => (j === i ? e.target.value : x)))} className="rounded-lg border border-line bg-surface px-2.5 py-2 text-sm text-ink" />
                </label>
              ))}
            </div>
          </div>
        )}
        {error && <p role="alert" className="text-sm text-claim">{error}</p>}
        <div className="flex gap-2">
          {!isOwner && (
            <button type="button" onClick={() => setProposing((p) => !p)} aria-pressed={proposing}
              className={`shrink-0 rounded-lg border px-3 text-sm ${proposing ? "border-vault bg-vault-soft text-vault" : "border-line text-muted hover:text-ink"}`}>
              {proposing ? "Cancel visit" : "Visit"}
            </button>
          )}
          <label htmlFor="msg" className="sr-only">Message</label>
          <input id="msg" value={text} onChange={(e) => setText(e.target.value)} placeholder={proposing ? "Add a note (optional)" : `Message ${other}`}
            className="min-w-0 flex-1 rounded-lg border border-line px-3 py-2.5 text-[15px] focus:border-vault focus:outline-none" />
          <button type="submit" className="shrink-0 rounded-lg bg-vault px-4 text-sm font-medium text-white hover:bg-vault-deep">
            {proposing ? "Send request" : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
function Inbox() {
  const { user } = useAuth();
  const router = useRouter();
  const active = useSearchParams().get("c");
  const list = useStore(() => (user ? conversationsFor(user.id) : []), [user?.id]);
  const current = active ? getConversation(active) : undefined;
  useEffect(() => {
    if (!active && list.length && window.matchMedia("(min-width: 768px)").matches) router.replace(`/messages?c=${list[0].id}`);
  }, [active, list, router]);
  if (!user) return null;
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-3xl">Messages</h1>
      {list.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line p-10 text-center text-sm text-muted">
          {user.accountType === "owner"
            ? "When someone messages you about a listing, the conversation appears here."
            : <>No conversations yet. Open a home from <Link href="/search" className="text-vault hover:underline">search</Link> and message the owner or request a visit.</>}
        </div>
      ) : (
        <div className="grid overflow-hidden rounded-2xl border border-line bg-surface md:grid-cols-[300px_minmax(0,1fr)]">
          <ul className={`${current ? "hidden md:block" : ""} divide-y divide-line border-line md:border-r`} aria-label="Conversations">
            {list.map((c) => {
              const last = lastMessage(c.id);
              const unread = isUnread(c, user.id);
              const other = user.id === c.ownerId ? c.seekerName : c.ownerName;
              return (
                <li key={c.id}>
                  <Link href={`/messages?c=${c.id}`} aria-current={c.id === active ? "true" : undefined}
                    className={`flex flex-col gap-0.5 px-4 py-3 ${c.id === active ? "bg-vault-soft" : "hover:bg-mist"}`}>
                    <span className="flex items-center justify-between gap-2">
                      <span className={`truncate ${unread ? "font-semibold" : "font-medium"}`}>{other}</span>
                      <span className="shrink-0 text-xs text-muted">{last ? formatTime(last.createdAt) : ""}</span>
                    </span>
                    <span className="truncate text-xs text-muted">{c.listingTitle}</span>
                    <span className={`flex items-center gap-1.5 truncate text-sm ${unread ? "text-ink" : "text-muted"}`}>
                      {unread && <span className="h-2 w-2 shrink-0 rounded-full bg-vault" aria-label="Unread" />}
                      {last ? (last.kind === "visit" ? "Visit request" : last.text) : "No messages yet"}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
          <section className={current ? "" : "hidden md:block"}>
            {current ? <Thread c={current} /> : <p className="p-10 text-center text-sm text-muted">Choose a conversation.</p>}
          </section>
        </div>
      )}
    </div>
  );
}
export default function MessagesPage() { // messages
  return (
    <Suspense>
      <Inbox />
    </Suspense>
  );
}
