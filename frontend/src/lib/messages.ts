"use client";
import type { User } from "./auth";
import type { Listing } from "./listings";
import { api, apiMode } from "./api";
import { readStore, uid, writeStore } from "./local-store";
import { KEYS, refreshInbox } from "./sync";
export interface Conversation {
  id: string;
  listingId: string;
  listingTitle: string;
  listingArea: string;
  seekerId: string;
  seekerName: string;
  ownerId: string;
  ownerName: string;
  createdAt: string;
  updatedAt: string;
  lastRead: Record<string, string>;
}
export interface VisitRequest {
  slots: string[];
  status: "pending" | "accepted" | "declined";
  acceptedSlot?: string;
}
export interface Message {
  id: string;
  conversationId: string;
  senderId: string;
  senderName: string;
  kind: "text" | "visit";
  text?: string;
  visit?: VisitRequest;
  createdAt: string;
}
const CONV_KEY = apiMode ? KEYS.conversations : "trustrent-conversations";
const MSG_KEY = apiMode ? KEYS.messages : "trustrent-messages";
const convs = () => readStore<Conversation[]>(CONV_KEY, []);
const msgs = () => readStore<Message[]>(MSG_KEY, []);
export function ownerIdOf(l: Listing) {
  return l.owner_id ?? `sample:${l.landlord.name}`;
}
export function conversationsFor(userId: string): Conversation[] {
  return convs()
    .filter((c) => c.seekerId === userId || c.ownerId === userId)
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}
export function getConversation(id: string) {
  return convs().find((c) => c.id === id);
}
export function messagesIn(conversationId: string): Message[] {
  return msgs().filter((m) => m.conversationId === conversationId).sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}
export function lastMessage(conversationId: string): Message | undefined {
  return messagesIn(conversationId).at(-1);
}
export function isUnread(c: Conversation, userId: string): boolean {
  const last = lastMessage(c.id);
  if (!last || last.senderId === userId) return false;
  return !c.lastRead[userId] || c.lastRead[userId] < last.createdAt;
}
export function unreadCount(userId: string): number {
  return conversationsFor(userId).filter((c) => isUnread(c, userId)).length;
}
export function markRead(conversationId: string, userId: string) {
  const list = convs();
  const c = list.find((x) => x.id === conversationId);
  if (!c) return;
  const now = new Date().toISOString();
  if (c.lastRead[userId] && c.lastRead[userId] >= (lastMessage(c.id)?.createdAt ?? "")) return;
  if (apiMode) api(`/conversations/${conversationId}/read`, { method: "POST" }).catch(() => {});
  writeStore(CONV_KEY, list.map((x) => (x.id === conversationId ? { ...x, lastRead: { ...x.lastRead, [userId]: now } } : x)));
}
export async function openConversation(listing: Listing, seeker: User): Promise<Conversation> {
  if (apiMode) {
    const c = await api<Conversation>("/conversations", { json: { listingId: listing.id } });
    await refreshInbox();
    return c;
  }
  const existing = convs().find((c) => c.listingId === listing.id && c.seekerId === seeker.id);
  if (existing) return existing;
  const now = new Date().toISOString();
  const c: Conversation = {
    id: uid("C"),
    listingId: listing.id,
    listingTitle: listing.title,
    listingArea: `${listing.locality}, ${listing.city}`,
    seekerId: seeker.id,
    seekerName: `${seeker.firstName} ${seeker.lastName}`,
    ownerId: ownerIdOf(listing),
    ownerName: listing.owner_name ?? listing.landlord.name,
    createdAt: now,
    updatedAt: now,
    lastRead: {},
  };
  writeStore(CONV_KEY, [c, ...convs()]);
  return c;
}
function append(m: Omit<Message, "id" | "createdAt">): Message {
  const msg: Message = { ...m, id: uid("M"), createdAt: new Date().toISOString() };
  writeStore(MSG_KEY, [...msgs(), msg]);
  writeStore(CONV_KEY, convs().map((c) => (c.id === m.conversationId
    ? { ...c, updatedAt: msg.createdAt, lastRead: { ...c.lastRead, [m.senderId]: msg.createdAt } }
    : c)));
  return msg;
}
export async function sendText(c: Conversation, sender: User, text: string) {
  if (apiMode) {
    await api(`/conversations/${c.id}/messages`, { json: { kind: "text", text: text.trim() } });
    await refreshInbox();
    return;
  }
  const msg = append({ conversationId: c.id, senderId: sender.id, senderName: `${sender.firstName} ${sender.lastName}`, kind: "text", text: text.trim() });
  demoOwnerReply(c, msg);
  return msg;
}
export async function requestVisit(c: Conversation, sender: User, slots: string[], note: string) {
  if (apiMode) {
    await api(`/conversations/${c.id}/messages`, { json: { kind: "visit", slots, text: note.trim() || null } });
    await refreshInbox();
    return;
  }
  const msg = append({
    conversationId: c.id, senderId: sender.id, senderName: `${sender.firstName} ${sender.lastName}`,
    kind: "visit", text: note.trim() || undefined, visit: { slots, status: "pending" },
  });
  demoOwnerReply(c, msg);
  return msg;
}
export async function respondToVisit(messageId: string, responder: User, accept: boolean, slot?: string) {
  if (apiMode) {
    await api(`/messages/${messageId}/visit-response`, { json: { accept, slot: slot ?? null } });
    await refreshInbox();
    return;
  }
  const list = msgs();
  const m = list.find((x) => x.id === messageId);
  if (!m?.visit) return;
  writeStore(MSG_KEY, list.map((x) => (x.id === messageId
    ? { ...x, visit: { ...x.visit!, status: accept ? "accepted" : "declined", acceptedSlot: accept ? slot : undefined } }
    : x)));
  const c = getConversation(m.conversationId);
  if (c) {
    append({
      conversationId: c.id, senderId: responder.id, senderName: `${responder.firstName} ${responder.lastName}`, kind: "text",
      text: accept && slot ? `Visit confirmed for ${formatSlot(slot)}. See you then.` : "Sorry, those times don't work for me. Could you suggest others?",
    });
  }
}
function demoOwnerReply(c: Conversation, incoming: Message) {
  if (apiMode || !c.ownerId.startsWith("sample:")) return;
  const owner = { id: c.ownerId, firstName: c.ownerName.split(" ")[0], lastName: c.ownerName.split(" ").slice(1).join(" ") } as User;
  window.setTimeout(() => {
    if (incoming.kind === "visit" && incoming.visit) {
      respondToVisit(incoming.id, owner, true, incoming.visit.slots[0]);
    } else if (messagesIn(c.id).filter((m) => m.senderId === c.ownerId).length === 0) {
      append({
        conversationId: c.id, senderId: c.ownerId, senderName: c.ownerName, kind: "text",
        text: `Hi! Thanks for your interest in ${c.listingTitle}. It's still available. Send me a visit request with a few times that suit you.`,
      });
    }
  }, 1500);
}
export function formatSlot(iso: string) {
  return new Date(iso).toLocaleString("en-IN", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}
export function formatTime(iso: string) {
  const d = new Date(iso);
  const sameDay = d.toDateString() === new Date().toDateString();
  return sameDay
    ? d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })
    : d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}
export function hasConfirmedVisit(listingId: string, userId: string): boolean {
  return conversationsFor(userId)
    .filter((c) => c.listingId === listingId && c.seekerId === userId)
    .some((c) => messagesIn(c.id).some((m) => m.kind === "visit" && m.visit?.status === "accepted"));
}
