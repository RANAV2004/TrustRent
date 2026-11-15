"use client";
import { useEffect, useState } from "react";
import { Loading, PageHeader, when } from "@/components/admin-ui";
import { auditLog, AuditRow } from "@/lib/trust";

export default function AdminAuditPage() { // audit log
  const [q, setQ] = useState({ action: "", actor: "", target: "", page: 1 });
  const [data, setData] = useState<{ total: number; actions: string[]; rows: AuditRow[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const t = setTimeout(() => auditLog(q).then(setData, (e) => setError(e.message)), 250);
    return () => clearTimeout(t);
  }, [q]);
  const pages = data ? Math.max(1, Math.ceil(data.total / 50)) : 1;
  const field = "rounded-lg border border-line bg-surface px-3 py-2 text-sm";
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Audit log" intro="Every admin, arbitrator and automatic action: who did it, when, to what, and from which IP address. Entries can't be edited from the console." />
      <div className="flex flex-wrap gap-2">
        <select value={q.action} onChange={(e) => setQ({ ...q, action: e.target.value, page: 1 })} aria-label="Action" className={field}>
          <option value="">All actions</option>
          {data?.actions.map((a) => <option key={a}>{a}</option>)}
        </select>
        <input value={q.actor} onChange={(e) => setQ({ ...q, actor: e.target.value, page: 1 })} placeholder="Who (email)" aria-label="Who" className={field} />
        <input value={q.target} onChange={(e) => setQ({ ...q, target: e.target.value.trim(), page: 1 })} placeholder="Target ID (user, deposit, listing)" aria-label="Target ID" className={`${field} sm:w-72`} />
      </div>
      {!data ? <Loading error={error} /> : (
        <>
          <div className="overflow-x-auto rounded-xl border border-line bg-surface">
            <table className="w-full text-left text-sm">
              <thead className="bg-mist text-xs text-muted uppercase"><tr><th className="px-3 py-2">When</th><th className="px-3 py-2">Who</th><th className="px-3 py-2">Action</th><th className="px-3 py-2">Target</th><th className="px-3 py-2">Details</th></tr></thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.id} className="border-t border-line align-top">
                    <td className="px-3 py-2 whitespace-nowrap">{when(r.at, true)}</td>
                    <td className="px-3 py-2">{r.actor}{r.ip && <span className="block text-xs text-muted">{r.ip}</span>}</td>
                    <td className="px-3 py-2 font-mono text-xs">{r.action}</td>
                    <td className="px-3 py-2 text-xs break-all">{r.targetType ? `${r.targetType} ` : ""}
                      {r.targetId && <button type="button" onClick={() => setQ({ ...q, target: r.targetId!, page: 1 })} className="text-vault hover:underline">{r.targetId}</button>}</td>
                    <td className="px-3 py-2 text-xs break-all text-muted">{Object.entries(r.details).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-muted">{data.total} entries</span>
            <button type="button" disabled={q.page <= 1} onClick={() => setQ({ ...q, page: q.page - 1 })} className="rounded border border-line px-2 py-1 disabled:opacity-40">Newer</button>
            <span>Page {q.page} of {pages}</span>
            <button type="button" disabled={q.page >= pages} onClick={() => setQ({ ...q, page: q.page + 1 })} className="rounded border border-line px-2 py-1 disabled:opacity-40">Older</button>
          </div>
        </>
      )}
    </div>
  );
}
