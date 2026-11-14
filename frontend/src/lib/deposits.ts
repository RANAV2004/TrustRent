"use client";
import { api, API_URL, ApiError, getToken } from "./api";
import type { User } from "./auth";
export interface Receipt {
  network: string | null;
  recordHash: string | null;
  recordTx: string | null;
  recordUrl: string | null;
  settleHash: string | null;
  settleTx: string | null;
  settleUrl: string | null;
}
export interface Deposit {
  id: string;
  amount: number;
  currency: "INR";
  status: "held" | "settlement_proposed" | "disputed" | "settling" | "settled";
  paidAt: string;
  listing: { id: string; title: string; area: string };
  deducted: number | null;
  refunded: number | null;
  reason: string | null;
  proposedAt: string | null;
  settledAt: string | null;
  movedOutAt?: string | null;
  disputedAt?: string | null;
  respondBy?: string | null;
  claimBy?: string | null;
  ownerAsked?: number | null;
  autoSettled?: boolean;
  receipt: Receipt;
  role: "tenant" | "owner" | "admin" | null;
  tenant?: { id: string; name: string };
  owner?: { id: string; name: string };
  ownerPayout?: "due" | "paid" | null;
  refundRef?: string | null;
  payment?: { provider: string; reference: string | null };
  verification?: { ledgerIntact: boolean; detailsMatch: boolean; verified: boolean; onChain: boolean };
}
export const STATUS_LABEL: Record<Deposit["status"], string> = {
  held: "Held safely",
  settlement_proposed: "Settlement proposed",
  disputed: "Disputed: admin will settle",
  settling: "Refund in progress",
  settled: "Settled",
};
export const networkLabel = (n: string | null) =>
  n === "polygon-amoy" ? "Polygon Amoy blockchain" : n ? "TrustRent ledger (hash-chained)" : "";
export const myDeposits = () => api<Deposit[]>("/deposits");
export const lookupDeposit = (q: string) => api<Deposit>(`/deposits/lookup?q=${encodeURIComponent(q.trim())}`);
export const proposeSettlement = (id: string, deducted: number, reason: string) =>
  api<Deposit>(`/deposits/${id}/propose`, { json: { deducted, reason } });
export const respondToSettlement = (id: string, accept: boolean) =>
  api<Deposit>(`/deposits/${id}/respond`, { json: { accept } });
export const markMovedOut = (id: string) => api<Deposit>(`/deposits/${id}/move-out`, { method: "POST" });
export interface Note { id: string; role: "tenant" | "owner" | "admin"; author: string; text: string; at: string }
export const listNotes = (id: string) => api<{ notes: Note[]; canAdd: boolean }>(`/deposits/${id}/notes`);
export const addNote = (id: string, text: string) => api<{ notes: Note[] }>(`/deposits/${id}/notes`, { json: { text } });
export interface AgreementTerms {
  startDate: string; months: number; monthlyRent: number; rentDueDay: number; noticeDays: number; lockInMonths: number;
  maintenance: string; extraClauses: string;
}
export interface AgreementView {
  agreement: null | {
    id: string; terms: AgreementTerms; text: string; textHash: string; createdAt: string;
    status: "draft" | "partly_signed" | "signed"; verified: boolean;
    signatures: { role: "tenant" | "owner"; typedName: string; signedAt: string; textHash: string; receipt: string | null }[];
  };
  canCreate: boolean;
  canSign?: boolean;
  signAs?: string | null;
}
export const getAgreement = (id: string) => api<AgreementView>(`/deposits/${id}/agreement`);
export const saveAgreement = (id: string, terms: AgreementTerms) => api<AgreementView>(`/deposits/${id}/agreement`, { json: terms });
export const signAgreement = (id: string, typedName: string) =>
  api<AgreementView>(`/deposits/${id}/agreement/sign`, { json: { typedName, agree: true } });
export interface PhotoRef { id: string; note: string | null; at: string; fileHash: string; url: string }
export interface Workspace {
  deposit: Deposit;
  tenant: { id: string; name: string; email: string; phone: string; verified: boolean } | null;
  owner: { id: string; name: string; email: string; phone: string; verified: boolean } | null;
  ownerAsked: number | null;
  payment: { provider: string; reference: string | null } | null;
  notes: Note[];
  photos: Record<string, Record<"move_in" | "move_out", Record<"tenant" | "owner", PhotoRef[]>>>;
  chat: { from: "tenant" | "owner"; text: string; at: string }[];
  timeline: { at: string; kind: string; text: string }[];
  ledger: { seq: number; kind: string; hash: string; at: string }[];
  canDecide: boolean;
}
export const getWorkspace = (id: string) => api<Workspace>(`/admin/deposits/${id}/workspace`);
export const adminDeposits = () => api<Deposit[]>("/admin/deposits");
export const adminSettle = (id: string, deducted: number, reason: string) =>
  api<Deposit>(`/admin/deposits/${id}/settle`, { json: { deducted, reason } });
export const adminRecordDeposit = (body: { tenant: string; listingId: string; amount: number; transactionId: string }) =>
  api<Deposit>("/admin/deposits", { json: body });
export const markOwnerPaid = (id: string) => api<Deposit>(`/admin/deposits/${id}/owner-paid`, { method: "POST" });
export interface Order {
  orderId: string;
  provider: "razorpay" | "demo";
  keyId: string | null;
  amount: number;
  currency: "INR";
  description: string;
  prefill: { name: string; email: string; contact: string };
}
export interface PaymentResult {
  user: User;
  payment: { id: string; status: string; purpose: string };
  depositId?: string | null;
}
export const createOrder = (body: { purpose: "premium"; planId: string } | { purpose: "deposit"; listingId: string }) =>
  api<Order>("/payments/order", { json: body });
export const verifyPayment = (orderId: string, paymentId?: string, signature?: string) =>
  api<PaymentResult>("/payments/verify", { json: { orderId, paymentId, signature } });
export async function agreementDocumentUrl(id: string): Promise<string> { // printable agreement (needs the token)
  const token = getToken();
  const res = await fetch(`${API_URL}/deposits/${id}/agreement/document`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError("Couldn't open the agreement.", res.status);
  return URL.createObjectURL(await res.blob());
}
