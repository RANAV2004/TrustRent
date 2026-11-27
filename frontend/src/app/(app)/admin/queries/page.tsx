"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Loading, PageHeader, Search } from "@/components/admin-ui";
import { StatusPill } from "@/components/support-ui";
import { adminTickets, TicketStatus, TicketSummary, when } from "@/lib/support";

const FILTERS: [TicketStatus | "", string][] = [["open", "Open"], ["in_progress", "In progress"], ["closed", "Closed"], ["", "All"]];

export default function AdminQueries() {
  const [filter, setFilter] = useState<TicketStatus | "">("open");
  const [q, setQ] = useState("");
  const [data, setData] = useState<{ tickets: TicketSummary[]; counts: Record<TicketStatus, number> } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => { adminTickets(filter, q).then(setData, (e) => setError(e.message)); }, [filter, q]);
  useEffect(() => {
    const t = window.setTimeout(load, q ? 300 : 0);
    return () => window.clearTimeout(t);
  }, [load, q]);
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Queries" intro="Problems users raised from Help & support. Reply on the ticket (they get an email), then close it with a resolution note.">
        <Search value={q} onChange={setQ} placeholder="Ticket number, subject or email" />
      </PageHeader>
      <div className="flex flex-wrap gap-2">
        {FILTERS.map(([f, label]) => (
          <button key={label} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}
            className={`rounded-full border px-3 py-1 text-sm ${filter === f ? "border-vault bg-vault-soft text-vault" : "border-line bg-surface text-muted hover:text-ink"}`}>
            {label}{f && data ? ` (${data.counts[f]})` : ""}
          </button>
        ))}
      </div>
      {!data ? <Loading error={error} /> : !data.tickets.length ? (
        <p className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">{q ? "No queries match your search." : "Nothing here."}</p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-line bg-surface">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="text-xs text-muted uppercase">
              <tr><th className="px-4 py-3 font-medium">Ticket</th><th className="px-4 py-3 font-medium">Problem</th><th className="px-4 py-3 font-medium">User</th><th className="px-4 py-3 font-medium">Status</th><th className="px-4 py-3 font-medium">Updated</th></tr>
            </thead>
            <tbody>
              {data.tickets.map((t) => (
                <tr key={t.ticketNo} className="border-t border-line align-top hover:bg-mist/50">
                  <td className="px-4 py-3"><Link href={`/help/${t.ticketNo}`} className="font-mono font-medium text-vault hover:underline">{t.ticketNo}</Link></td>
                  <td className="px-4 py-3"><p className="font-medium">{t.subject}</p><p className="text-xs text-muted">{t.category}</p></td>
                  <td className="px-4 py-3"><p>{t.user?.name}</p><p className="text-xs text-muted">{t.user?.email} · {t.user?.accountType}</p></td>
                  <td className="px-4 py-3"><StatusPill status={t.status} label={t.statusLabel} /></td>
                  <td className="px-4 py-3 text-xs text-muted">{when(t.updatedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {error && data && <p role="alert" className="text-sm text-claim">{error}</p>}
    </div>
  );
}
