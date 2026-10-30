"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Loading, PageHeader, Stat } from "@/components/admin-ui";
import { AdminOverview, getOverview } from "@/lib/admin";
import { formatINR } from "@/lib/format";
function Group({ title, href, children }: { title: string; href: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg">{title}</h2>
        <Link href={href} className="text-sm text-vault hover:underline">Open</Link>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{children}</div>
    </section>
  );
}
export default function AdminOverviewPage() { // admin overview
  const [o, setO] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { getOverview().then(setO, (e) => setError(e.message)); }, []);
  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="Overview" intro="Everything in the TrustRent database at a glance." />
      {!o ? <Loading error={error} /> : (
        <>
          {o.pendingVerifications > 0 && (
            <Link href="/admin/verifications" className="rounded-xl border border-[#E8D3A8] bg-amber-soft px-4 py-3 text-sm text-amber hover:border-amber">
              <strong>{o.pendingVerifications}</strong> verification request{o.pendingVerifications === 1 ? " is" : "s are"} waiting for a decision
            </Link>
          )}
          <Group title="Users" href="/admin/users">
            <Stat label="Accounts" value={o.users.total} note={`${o.users.seekers} looking, ${o.users.owners} owners`} />
            <Stat label="ID verified" value={o.users.verified} tone="good" />
            <Stat label="Premium now" value={o.users.premium} />
            <Stat label="Banned" value={o.users.banned} note={`${o.users.deleted} deleted`} tone={o.users.banned ? "warn" : undefined} />
          </Group>
          <Group title="Listings" href="/admin/listings">
            <Stat label="Live" value={o.listings.live} tone="good" />
            <Stat label="Paused by owner" value={o.listings.paused} />
            <Stat label="Unlisted by admin" value={o.listings.unlisted} tone={o.listings.unlisted ? "warn" : undefined} />
            <Stat label="Removed" value={o.listings.removed} />
          </Group>
          <Group title="Deposits" href="/admin/deposits">
            <Stat label="Receipts" value={o.deposits.count} />
            <Stat label="Held now" value={formatINR(o.deposits.held)} note={`${o.deposits.open} open`} />
            <Stat label="Disputed" value={o.deposits.disputed} tone={o.deposits.disputed ? "warn" : undefined} />
            <Stat label="Refunded" value={formatINR(o.deposits.refunded)} />
          </Group>
          <Group title="Messages & Premium" href="/admin/premium">
            <Stat label="Conversations" value={o.conversations} />
            <Stat label="Messages" value={o.messages} />
            <Stat label="Premium members" value={o.users.premium} />
            <Stat label="Premium revenue" value={formatINR(o.premiumRevenue)} tone="good" />
          </Group>
        </>
      )}
    </div>
  );
}
