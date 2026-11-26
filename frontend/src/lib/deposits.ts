"use client";
import { api } from "./api";
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
  status: "held" | "settlement_proposed" | "disputed" | "settled";
  paidAt: string;
  listing: { id: string; title: string; area: string };
  deducted: number | null;
  refunded: number | null;
  reason: string | null;
  proposedAt: string | null;
  settledAt: string | null;
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
