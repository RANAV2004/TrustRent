"use client";
import { useEffect, useState } from "react";
import { api, API_URL, getToken } from "./api";

export type TicketStatus = "open" | "in_progress" | "closed";
export interface TicketSummary {
  ticketNo: string; category: string; subject: string; status: TicketStatus; statusLabel: string;
  createdAt: string; updatedAt: string; closedAt: string | null;
  user?: { id: string; name: string; email: string; username: string; accountType: string };
}
export interface TicketImage { id: string; fileName: string; size: number }
export interface TimelineEntry {
  id: string; kind: "message" | "status"; fromSupport: boolean; statusTo: TicketStatus | null; statusLabel: string | null;
  text: string | null; createdAt: string; author: string; images: TicketImage[];
}
export interface Ticket extends TicketSummary {
  description: string; pageUrl: string | null; resolution: string | null; canReply: boolean; isSupport: boolean;
  images: TicketImage[]; timeline: TimelineEntry[];
}

export const CATEGORIES = [
  "Account and sign-in", "Payments and Premium", "Deposits and refunds", "Listings and messages",
  "Verification", "Lawyers and agreements", "Something isn't working", "Other",
];
export const MAX_IMAGES = 5;
export const MAX_IMAGE_MB = 5;

export const raiseTicket = (form: FormData) => api<Ticket>("/support/tickets", { form });
export const myTickets = () => api<TicketSummary[]>("/support/tickets");
export const getTicket = (no: string) => api<Ticket>(`/support/tickets/${encodeURIComponent(no.trim())}`);
export function replyToTicket(no: string, text: string, images: File[]) {
  const form = new FormData();
  form.append("text", text);
  images.forEach((f) => form.append("images", f));
  return api<Ticket>(`/support/tickets/${encodeURIComponent(no)}/messages`, { form });
}
export const adminTickets = (status: string, q: string) =>
  api<{ tickets: TicketSummary[]; counts: Record<TicketStatus, number> }>(`/admin/support?${new URLSearchParams({ status, q })}`);
export const setTicketStatus = (no: string, status: TicketStatus, note: string) =>
  api<Ticket>(`/admin/support/${encodeURIComponent(no)}/status`, { json: { status, note } });

export function useTicketImage(ticketNo: string, imageId: string): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let objectUrl: string | null = null;
    let alive = true;
    fetch(`${API_URL}/support/tickets/${encodeURIComponent(ticketNo)}/images/${imageId}`, { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((r) => (r.ok ? r.blob() : null))
      .then((b) => { if (b && alive) { objectUrl = URL.createObjectURL(b); setUrl(objectUrl); } })
      .catch(() => {});
    return () => { alive = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [ticketNo, imageId]);
  return url;
}

export const STATUS_TONE: Record<TicketStatus, string> = {
  open: "bg-amber-soft text-amber", in_progress: "bg-vault-soft text-vault", closed: "bg-mist text-muted",
};
export const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }) : "";
