"use client";
import { useEffect, useState } from "react";
import { ConfirmAction, Loading, PageHeader, Pill, Stat, when } from "@/components/admin-ui";
import { AdminPremium, getPremium, revokePremium } from "@/lib/admin";
import { formatINR } from "@/lib/format";
const HOW = [
  "A verified user buys a plan. Payment goes through Razorpay (demo checkout in demo mode).",
  "For the plan's length they can message owners and book visits for brand-new homes in their first 48 hours, before everyone else.",
  "New homes still show in everyone's search, with a \"Premium only\" tag until the 48 hours end.",
  "Buying again adds days on top of the current plan. Plans don't renew by themselves.",
];
export default function AdminPremiumPage() { // admin premium
  const [data, setData] = useState<AdminPremium | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => getPremium().then(setData, (e) => setError(e.message));
  useEffect(() => { load(); }, []);
  const active = data?.members.filter((m) => m.premium?.active) ?? [];
  const revenue = data?.payments.reduce((a, p) => a + p.amount, 0) ?? 0;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Premium" intro="Who has Premium, which plan they bought and until when. Revoke it if a member misuses early access (for example, spamming owners)." />
      {!data ? <Loading error={error} /> : (
        <>
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <section className="rounded-xl border border-line bg-surface p-5">
              <h2 className="mb-2 text-lg">How Premium works</h2>
              <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-sm">{HOW.map((h) => <li key={h}>{h}</li>)}</ol>
            </section>
            <section className="rounded-xl border border-line bg-surface p-5">
              <h2 className="mb-2 text-lg">Plans</h2>
              <ul className="flex flex-col divide-y divide-line text-sm">
                {data.plans.map((p) => (
                  <li key={p.id} className="flex justify-between py-2"><span>{p.label} <span className="text-muted">({p.days} days)</span></span><span className="font-semibold tabular">{formatINR(p.price)}</span></li>
                ))}
              </ul>
            </section>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <Stat label="Active members" value={active.length} tone="good" />
            <Stat label="Expired or revoked" value={data.members.length - active.length} />
            <Stat label="Premium revenue" value={formatINR(revenue)} note={`${data.payments.length} payment${data.payments.length === 1 ? "" : "s"}`} />
          </div>
          <section>
            <h2 className="mb-3 text-lg">Members</h2>
            <div className="overflow-x-auto rounded-xl border border-line bg-surface">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-line bg-mist/60 text-xs text-muted uppercase">
                  <tr><th className="px-4 py-3">Member</th><th className="px-4 py-3">Plan</th><th className="px-4 py-3">Valid until</th><th className="px-4 py-3">Paid in total</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Action</th></tr>
                </thead>
                <tbody>
                  {data.members.map((m) => (
                    <tr key={m.id} className="border-b border-line align-top last:border-0">
                      <td className="px-4 py-3"><p className="font-medium">{m.name}</p><p className="text-xs break-all text-muted">{m.email}</p></td>
                      <td className="px-4 py-3">{m.premium?.plan}</td>
                      <td className="px-4 py-3 whitespace-nowrap">{when(m.premium?.until)}</td>
                      <td className="px-4 py-3 tabular">{formatINR(m.paid)}</td>
                      <td className="px-4 py-3">{m.premium?.active ? <Pill tone="amber">Active</Pill> : <Pill tone="grey">Ended</Pill>}{m.banned && <> <Pill tone="red">Banned</Pill></>}</td>
                      <td className="px-4 py-3">
                        {m.premium?.active
                          ? <ConfirmAction label="Revoke" confirmLabel="Revoke now" danger onConfirm={() => revokePremium(m.id).then(load)} />
                          : <span className="text-xs text-muted">NA</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data.members.length && <p className="p-6 text-center text-sm text-muted">No one has bought Premium yet.</p>}
            </div>
          </section>
          <section>
            <h2 className="mb-3 text-lg">Payments</h2>
            <ul className="flex flex-col divide-y divide-line rounded-xl border border-line bg-surface text-sm">
              {data.payments.map((p) => (
                <li key={p.id} className="flex flex-wrap justify-between gap-2 px-4 py-2.5">
                  <span>{p.user.name}, {p.plan}</span>
                  <span className="text-muted">{when(p.paidAt, true)}, {p.provider === "razorpay" ? "Razorpay" : "Demo"}, <strong className="text-ink tabular">{formatINR(p.amount)}</strong></span>
                </li>
              ))}
              {!data.payments.length && <li className="p-6 text-center text-muted">No payments yet.</li>}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
