"use client";
import { useState } from "react";
import { formatINR } from "@/lib/format";
import { Order, PaymentResult, verifyPayment } from "@/lib/deposits";
interface RazorpayResponse { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string }
interface RazorpayInstance { open(): void; on(event: string, cb: (r: { error?: { description?: string } }) => void): void }
declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
  }
}
const SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";
function loadRazorpay(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = SCRIPT;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Couldn't load the payment window. Check your connection."));
    document.body.appendChild(s);
  });
}
export function payWithRazorpay(order: Order): Promise<PaymentResult> { // pay with razorpay
  return loadRazorpay().then(() => new Promise<PaymentResult>((resolve, reject) => {
    const rzp = new window.Razorpay!({
      key: order.keyId,
      amount: order.amount * 100,
      currency: order.currency,
      order_id: order.orderId,
      name: "TrustRent",
      description: order.description,
      prefill: order.prefill,
      theme: { color: "#0D5B4C" },
      handler: (r: RazorpayResponse) => {
        verifyPayment(r.razorpay_order_id, r.razorpay_payment_id, r.razorpay_signature).then(resolve, reject);
      },
      modal: { ondismiss: () => reject(new Error("Payment cancelled.")) },
    });
    rzp.on("payment.failed", (r) => reject(new Error(r.error?.description || "Payment failed. No money was taken.")));
    rzp.open();
  }));
}
export function DemoCheckout({ order, onPaid, onCancel }: { order: Order; onPaid: (r: PaymentResult) => void; onCancel: () => void }) { // demo checkout
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5" role="dialog" aria-label="Demo checkout">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">Demo checkout, no money is taken</p>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm">{order.description}</span>
        <span className="font-display text-2xl font-semibold tabular">{formatINR(order.amount)}</span>
      </div>
      <p className="text-xs text-muted">With Razorpay keys on the server, this opens the real Razorpay window (UPI, cards, net banking).</p>
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
      <div className="flex gap-2">
        <button type="button" disabled={busy}
          onClick={() => { setBusy(true); setError(null); verifyPayment(order.orderId).then(onPaid, (e) => { setError(e.message); setBusy(false); }); }}
          className="rounded-lg bg-vault px-5 py-2.5 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">
          {busy ? "Processing..." : `Pay ${formatINR(order.amount)}`}
        </button>
        <button type="button" onClick={onCancel} className="px-3 text-sm text-muted hover:text-ink">Cancel</button>
      </div>
    </div>
  );
}
