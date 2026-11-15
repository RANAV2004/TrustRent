"use client";
import { useCallback, useEffect, useState } from "react";
import { ConfirmAction, Loading, PageHeader, Pill } from "@/components/admin-ui";
import { markOwnerPaid } from "@/lib/deposits";
import { formatINR } from "@/lib/format";
import { adminPayouts, rentPayoutPaid, revealPayout, reviewPayout } from "@/lib/trust";

type Desk = Awaited<ReturnType<typeof adminPayouts>>;

function Reveal({ userId }: { userId: string }) {
  const [v, setV] = useState<string | null>(null);
  if (v) return <code className="text-xs">{v}</code>;
  return <button type="button" onClick={() => revealPayout(userId).then((r) => setV(`${r.holderName} · A/c ${r.accountNumber} · ${r.ifsc} · PAN ${r.pan}`))}
    className="text-xs text-vault hover:underline">Show full details (logged)</button>;
}

export default function AdminPayoutsPage() { // payouts desk
  const [desk, setDesk] = useState<Desk | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [linked, setLinked] = useState<Record<string, string>>({});
  const load = useCallback(() => adminPayouts().then(setDesk, (e) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);
  if (!desk) return <Loading error={error} />;
  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="Owner payouts" intro={desk.routeEnabled
        ? "Razorpay Route is on: rent and deposit deductions go straight to each owner's linked account. Anything that couldn't be sent shows below."
        : "Razorpay Route is off: pay these owners by bank transfer, then mark them paid. Turn on RAZORPAY_ROUTE_ENABLED to automate it."} />
      <section className="flex flex-col gap-3">
        <h2 className="text-lg">Waiting to be paid ({desk.due.length})</h2>
        {desk.due.length === 0 ? <p className="text-sm text-muted">Nothing due.</p> : desk.due.map((x) => (
          <div key={x.kind + x.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface p-4 text-sm">
            <span className="flex flex-col">
              <span className="font-medium">{formatINR(x.amount)} to {x.owner.name}</span>
              <span className="text-xs text-muted">{x.kind === "rent" ? `Rent ${x.period}` : "Deposit deduction"} · {x.depositId}</span>
              {x.owner.account ? <span className="text-xs">A/c ending {x.owner.account.accountLast4} · {x.owner.account.ifsc} <Reveal userId={x.owner.id} /></span>
                : <span className="text-xs text-claim">The owner hasn&apos;t added bank details yet.</span>}
            </span>
            <ConfirmAction label="Mark paid" confirmLabel="I've paid this" onConfirm={() => (x.kind === "rent" ? rentPayoutPaid(x.id) : markOwnerPaid(x.id)).then(load)} />
          </div>
        ))}
      </section>
      <section className="flex flex-col gap-3">
        <h2 className="text-lg">Owner bank details</h2>
        {desk.accounts.length === 0 && <p className="text-sm text-muted">No owner has added bank details yet.</p>}
        {desk.accounts.map((a) => (
          <div key={a.user.id} className="flex flex-col gap-2 rounded-xl border border-line bg-surface p-4 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium">{a.user.name}</span>
              <Pill tone={a.status === "active" ? "green" : a.status === "rejected" ? "red" : "amber"}>{a.status}</Pill>
            </div>
            <p>{a.holderName} · {a.ifsc} · ending {a.accountLast4} · PAN ending {a.panLast4}{a.linkedAccountId ? ` · Route ${a.linkedAccountId}` : ""} <Reveal userId={a.user.id} /></p>
            {a.status === "submitted" && (
              <div className="flex flex-wrap items-center gap-2">
                <input value={linked[a.user.id] ?? ""} onChange={(e) => setLinked({ ...linked, [a.user.id]: e.target.value.trim() })}
                  placeholder={desk.routeEnabled ? "Razorpay linked account id (acc_...)" : "Linked account id (optional)"} aria-label="Linked account id"
                  className="w-72 rounded-lg border border-line px-3 py-1.5" />
                <ConfirmAction label="Approve" confirmLabel="Approve details" onConfirm={() => reviewPayout(a.user.id, true, linked[a.user.id] ?? "", "").then(load)} />
                <ConfirmAction label="Reject" confirmLabel="Reject" danger reasonPlaceholder="Reason for the owner" onConfirm={(r) => reviewPayout(a.user.id, false, "", r).then(load)} />
              </div>
            )}
            {desk.routeEnabled && a.status === "submitted" && (
              <p className="text-xs text-muted">Create the linked account in Razorpay Dashboard → Route → Linked Accounts with these details (Razorpay runs its KYC), then paste its id.</p>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}
