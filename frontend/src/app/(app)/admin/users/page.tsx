"use client";
import { useEffect, useMemo, useState } from "react";
import { ConfirmAction, Loading, PageHeader, Pill, Search, when } from "@/components/admin-ui";
import { AdminUser, banUser, deleteUser, getUsers, unbanUser } from "@/lib/admin";
type Filter = "all" | "seeker" | "owner" | "premium" | "banned";
const FILTERS: [Filter, string][] = [["all", "All"], ["seeker", "Looking for a home"], ["owner", "Owners"], ["premium", "Premium"], ["banned", "Banned"]];
export default function AdminUsersPage() { // admin users
  const [rows, setRows] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const load = () => getUsers().then(setRows, (e) => setError(e.message));
  useEffect(() => { load(); }, []);
  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    return (rows ?? []).filter((u) => !u.deletedAt || filter === "all").filter((u) =>
      filter === "all" ? true : filter === "premium" ? u.premium?.active : filter === "banned" ? !!u.banned : u.accountType === filter && !u.isAdmin,
    ).filter((u) => !t || [u.name, u.username, u.email, u.phone].some((v) => v.toLowerCase().includes(t)));
  }, [rows, q, filter]);
  const replace = (u: AdminUser) => setRows((l) => l!.map((x) => (x.id === u.id ? { ...x, ...u, listings: x.listings, deposits: x.deposits } : x)));
  return (
    <div>
      <PageHeader title="Users" intro="Every account on TrustRent. Banning stops someone signing in and hides their listings. Deleting removes their personal details and documents but keeps deposit receipts and payments, which must be kept." />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Search value={q} onChange={setQ} placeholder="Search name, username, email or phone" />
        <div className="flex flex-wrap gap-1">
          {FILTERS.map(([f, label]) => (
            <button key={f} type="button" onClick={() => setFilter(f)} aria-pressed={filter === f}
              className={`rounded-full border px-3 py-1 text-sm ${filter === f ? "border-vault bg-vault-soft text-vault" : "border-line bg-surface text-muted hover:text-ink"}`}>{label}</button>
          ))}
        </div>
      </div>
      {!rows ? <Loading error={error} /> : (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-line bg-mist/60 text-xs text-muted uppercase">
              <tr><th className="px-4 py-3">User</th><th className="px-4 py-3">Contact</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Joined</th><th className="px-4 py-3">Actions</th></tr>
            </thead>
            <tbody>
              {shown.map((u) => (
                <tr key={u.id} className={`border-b border-line last:border-0 align-top ${u.deletedAt ? "text-muted" : ""}`}>
                  <td className="px-4 py-3">
                    <p className="font-medium">{u.name}</p>
                    <p className="text-xs text-muted">{[u.username && `@${u.username}`, u.isDemo && "sample account"].filter(Boolean).join(", ")}</p>
                  </td>
                  <td className="px-4 py-3"><p className="break-all">{u.email}</p><p className="text-xs text-muted">{u.phone}</p></td>
                  <td className="px-4 py-3">
                    {u.isAdmin ? <Pill tone="dark">Admin</Pill> : u.accountType === "owner" ? "Owner" : "Looking for a home"}
                    <p className="text-xs text-muted">{u.listings} listing{u.listings === 1 ? "" : "s"}, {u.deposits} deposit{u.deposits === 1 ? "" : "s"}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex flex-wrap gap-1">
                      {u.deletedAt ? <Pill tone="grey">Deleted</Pill> : u.banned ? <Pill tone="red">Banned</Pill> : <Pill tone="green">Active</Pill>}
                      {u.verified && <Pill tone="green">ID verified</Pill>}
                      {u.premium?.active && <Pill tone="amber">Premium ({u.premium.plan})</Pill>}
                    </span>
                    {u.banned && !u.deletedAt && <p className="mt-1 text-xs text-claim">{u.banned.reason}</p>}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">{when(u.createdAt)}</td>
                  <td className="px-4 py-3">
                    {u.isAdmin || u.deletedAt ? <span className="text-xs text-muted">NA</span> : (
                      <span className="flex flex-col items-start gap-2">
                        {u.banned
                          ? <ConfirmAction key="unban" label="Unban" confirmLabel="Unban" onConfirm={() => unbanUser(u.id).then((r) => replace(r.user))} />
                          : <ConfirmAction key="ban" label="Ban" confirmLabel="Ban" danger reasonPlaceholder="Reason (shown in the log)" onConfirm={(reason) => banUser(u.id, reason).then((r) => replace(r.user))} />}
                        <ConfirmAction label="Delete" confirmLabel="Delete for good" danger onConfirm={() => deleteUser(u.id).then(load)} />
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!shown.length && <p className="p-6 text-center text-sm text-muted">No users match.</p>}
        </div>
      )}
    </div>
  );
}
