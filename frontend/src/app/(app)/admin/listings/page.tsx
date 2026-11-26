"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ConfirmAction, Loading, PageHeader, Pill, Search, when } from "@/components/admin-ui";
import { AdminListing, getAdminListings, relistListing, unlistListing } from "@/lib/admin";
import { formatINR } from "@/lib/format";
const STATUS: Record<AdminListing["status"], [string, "green" | "grey" | "red" | "amber"]> = {
  live: ["Live", "green"], paused: ["Paused by owner", "grey"], blocked: ["Unlisted by admin", "red"], removed: ["Removed", "grey"],
};
export default function AdminListingsPage() { // admin listings
  const [rows, setRows] = useState<AdminListing[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => { getAdminListings().then(setRows, (e) => setError(e.message)); }, []);
  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    return (rows ?? []).filter((x) => !t || [x.id, x.title, x.area, x.owner.name, x.owner.email].some((v) => v.toLowerCase().includes(t)));
  }, [rows, q]);
  const replace = (x: AdminListing) => setRows((l) => l!.map((r) => (r.id === x.id ? { ...r, status: x.status, adminNote: x.adminNote } : r)));
  return (
    <div>
      <PageHeader title="Listings" intro="Every home on TrustRent. Unlisting hides a home from search at once; the owner sees your reason and can't put it back up themselves." />
      <div className="mb-4"><Search value={q} onChange={setQ} placeholder="Search title, area, ID or owner" /></div>
      {!rows ? <Loading error={error} /> : (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-line bg-mist/60 text-xs text-muted uppercase">
              <tr><th className="px-4 py-3">Home</th><th className="px-4 py-3">Owner</th><th className="px-4 py-3">Rent and deposit</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Listed</th><th className="px-4 py-3">Actions</th></tr>
            </thead>
            <tbody>
              {shown.map((x) => (
                <tr key={x.id} className="border-b border-line align-top last:border-0">
                  <td className="px-4 py-3">
                    {x.status === "live" ? <Link href={`/listings/${x.id}`} className="font-medium hover:underline">{x.title}</Link> : <span className="font-medium">{x.title}</span>}
                    <p className="text-xs text-muted">{x.id}, {x.area}, {x.bhk} BHK{x.sample ? ", sample" : ""}</p>
                  </td>
                  <td className="px-4 py-3">{x.owner.name}{x.owner.banned && <> <Pill tone="red">Banned</Pill></>}<p className="text-xs break-all text-muted">{x.owner.email}</p></td>
                  <td className="px-4 py-3 tabular">{formatINR(x.rent)}<p className="text-xs text-muted">{formatINR(x.deposit)} deposit</p></td>
                  <td className="px-4 py-3">
                    <Pill tone={STATUS[x.status][1]}>{STATUS[x.status][0]}</Pill>
                    {x.adminNote && <p className="mt-1 max-w-56 text-xs text-muted">{x.adminNote}</p>}
                    <p className="mt-1 text-xs text-muted">{x.conversations} chat{x.conversations === 1 ? "" : "s"}</p>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">{when(x.listedAt)}</td>
                  <td className="px-4 py-3">
                    {x.status === "blocked"
                      ? <ConfirmAction key="relist" label="Relist" confirmLabel="Put back live" onConfirm={() => relistListing(x.id).then(replace)} />
                      : x.status === "removed" ? <span className="text-xs text-muted">NA</span>
                        : <ConfirmAction key="unlist" label="Unlist" confirmLabel="Unlist" danger reasonPlaceholder="Reason shown to the owner" onConfirm={(r) => unlistListing(x.id, r).then(replace)} />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!shown.length && <p className="p-6 text-center text-sm text-muted">No listings match.</p>}
        </div>
      )}
    </div>
  );
}
