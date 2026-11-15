"use client";
import { useCallback, useEffect, useState } from "react";
import { DemoCheckout, payWithRazorpay } from "@/components/checkout";
import { createOrder, Deposit, Order } from "@/lib/deposits";
import { formatINR } from "@/lib/format";
import { markRentPaid, openDocument, RentInvoice, RentSchedule, rentSchedule } from "@/lib/trust";

const monthName = (p: string) => new Date(p + "-01T00:00:00").toLocaleDateString("en-IN", { month: "long", year: "numeric" });
const TONE: Record<RentInvoice["status"], string> = {
  paid: "bg-vault-soft text-vault", due: "bg-mist text-ink", overdue: "bg-claim-soft text-claim", cancelled: "bg-mist text-muted",
};

export function RentPanel({ d }: { d: Deposit }) { // monthly rent
  const [s, setS] = useState<RentSchedule | null>(null);
  const [order, setOrder] = useState<Order | null>(null);
  const [offline, setOffline] = useState<string | null>(null);
  const [method, setMethod] = useState("upi");
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const load = useCallback(() => rentSchedule(d.id).then(setS, () => setS(null)), [d.id]);
  useEffect(() => { load(); }, [load]);
  if (!s || s.invoices.length === 0) return null;
  const next = s.invoices.find((i) => i.status === "due" || i.status === "overdue");
  async function pay(i: RentInvoice) {
    setError(null);
    try {
      const o = await createOrder({ purpose: "rent", invoiceId: i.id });
      if (o.provider === "razorpay") {
        await payWithRazorpay(o);
        await load();
      } else setOrder(o);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't start the payment.");
    }
  }
  async function recordOffline(id: string) {
    setError(null);
    try {
      await markRentPaid(id, method, reference);
      setOffline(null);
      setReference("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save.");
    }
  }
  const lastPaid = [...s.invoices].reverse().find((i) => i.status === "paid");
  const show = open ? s.invoices : s.invoices.filter((i) => i === next || i === lastPaid || i.status === "overdue").slice(0, 4);
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-line p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-medium">Monthly rent</h3>
        <span className="text-xs text-muted">Paid so far: {formatINR(s.paidTotal)}</span>
      </div>
      {order && (
        <DemoCheckout order={order} onCancel={() => setOrder(null)} onPaid={() => { setOrder(null); load(); }} />
      )}
      <ul className="flex flex-col divide-y divide-line text-sm">
        {show.map((i) => (
          <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <span className="flex flex-col">
              <span className="font-medium">{monthName(i.period)}</span>
              <span className="text-xs text-muted">{formatINR(i.amount)} · due {new Date(i.dueDate).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</span>
            </span>
            <span className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${TONE[i.status]}`}>{i.status}</span>
              {i.status === "paid" && (
                <button type="button" onClick={() => openDocument(`/rent/${i.id}/receipt`).catch((e) => setError(e.message))}
                  className="text-xs text-vault hover:underline">Receipt</button>
              )}
              {s.role === "tenant" && i.payable && (i.status === "due" || i.status === "overdue") && (
                <button type="button" onClick={() => pay(i)} className="rounded-lg bg-vault px-3 py-1.5 text-xs font-medium text-white hover:bg-vault-deep">Pay {formatINR(i.amount)}</button>
              )}
              {s.role === "owner" && (i.status === "due" || i.status === "overdue") && (
                <button type="button" onClick={() => setOffline(offline === i.id ? null : i.id)} className="text-xs text-vault hover:underline">Paid to me directly</button>
              )}
            </span>
            {offline === i.id && (
              <form onSubmit={(e) => { e.preventDefault(); recordOffline(i.id); }} className="flex w-full flex-wrap items-end gap-2 rounded-lg bg-mist p-3">
                <label className="flex flex-col gap-1 text-xs"><span className="text-muted">How</span>
                  <select value={method} onChange={(e) => setMethod(e.target.value)} className="rounded-lg border border-line bg-surface px-2 py-1.5">
                    <option value="upi">UPI</option><option value="bank">Bank transfer</option><option value="cash">Cash</option><option value="cheque">Cheque</option>
                  </select></label>
                <label className="flex flex-col gap-1 text-xs"><span className="text-muted">Reference (optional)</span>
                  <input value={reference} onChange={(e) => setReference(e.target.value)} maxLength={60} className="rounded-lg border border-line bg-surface px-2 py-1.5" /></label>
                <button type="submit" className="rounded-lg bg-vault px-3 py-1.5 text-xs font-medium text-white">Record and send receipt</button>
              </form>
            )}
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-3 text-xs">
        {s.invoices.length > show.length && <button type="button" onClick={() => setOpen(true)} className="text-vault hover:underline">Show all {s.invoices.length} months</button>}
        {s.financialYears.map((fy) => (
          <button key={fy} type="button" onClick={() => openDocument(`/deposits/${d.id}/rent/statement?fy=${fy}`).catch((e) => setError(e.message))}
            className="text-vault hover:underline">HRA statement FY {fy}-{String(fy + 1).slice(2)}</button>
        ))}
      </div>
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
    </section>
  );
}
