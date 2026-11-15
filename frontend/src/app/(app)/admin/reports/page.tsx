"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ConfirmAction, Loading, PageHeader, Pill, when } from "@/components/admin-ui";
import { Stars } from "@/components/review-panel";
import { AdminReport, adminReports, AdminReview, adminReviews, hideReview, resolveReport } from "@/lib/trust";

export default function AdminReportsPage() { // reports and reviews
  const [state, setState] = useState("open");
  const [rows, setRows] = useState<AdminReport[] | null>(null);
  const [reviews, setReviews] = useState<AdminReview[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    adminReports(state).then(setRows, (e) => setError(e.message));
    adminReviews().then(setReviews, () => setReviews([]));
  }, [state]);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="flex flex-col gap-8">
      <section>
        <PageHeader title="Reports" intro="Homes people reported. Three reports from different people pause a home automatically until you decide.">
          <select value={state} onChange={(e) => setState(e.target.value)} aria-label="Show" className="rounded-lg border border-line bg-surface px-3 py-2 text-sm">
            <option value="open">Open</option><option value="actioned">Unlisted</option><option value="dismissed">Dismissed</option><option value="all">All</option>
          </select>
        </PageHeader>
        {!rows ? <Loading error={error} /> : rows.length === 0 ? <p className="text-sm text-muted">Nothing here.</p> : (
          <ul className="flex flex-col gap-3">
            {rows.map((r) => (
              <li key={r.id} className="flex flex-col gap-2 rounded-xl border border-line bg-surface p-4 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="flex flex-wrap items-center gap-2">
                    <Link href={`/listings/${r.listing.id}`} className="font-medium hover:underline">{r.listing.title}</Link>
                    <Pill tone={r.listing.status === "live" ? "green" : r.listing.status === "blocked" ? "red" : "amber"}>{r.listing.status}</Pill>
                    {r.listing.openReports > 1 && <Pill tone="red">{r.listing.openReports} open reports</Pill>}
                  </span>
                  <span className="text-xs text-muted">{when(r.createdAt, true)}</span>
                </div>
                <p><strong>{r.reasonLabel}</strong>{r.details ? `: ${r.details}` : ""}</p>
                <p className="text-xs text-muted">Reported by {r.reporter.name}{r.resolution ? ` · Outcome: ${r.resolution}` : ""}</p>
                {r.status === "open" && (
                  <div className="flex flex-wrap gap-2">
                    <ConfirmAction label="Dismiss" confirmLabel="Dismiss report" reasonPlaceholder="Note (optional)"
                      onConfirm={(note) => resolveReport(r.id, "dismiss", note).then(load)} />
                    <ConfirmAction label="Unlist home" confirmLabel="Unlist" danger reasonPlaceholder="Reason shown to the owner"
                      onConfirm={(note) => resolveReport(r.id, "unlist", note).then(load)} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <PageHeader title="Reviews" intro="Reviews after settled deposits. Hide a review that shares personal details, is abusive or isn't about the tenancy." />
        {!reviews ? <Loading /> : reviews.length === 0 ? <p className="text-sm text-muted">No reviews yet.</p> : (
          <ul className="flex flex-col gap-2">
            {reviews.map((r) => (
              <li key={r.id} className="flex flex-wrap items-start justify-between gap-2 rounded-xl border border-line bg-surface p-3 text-sm">
                <span className="flex flex-col">
                  <span><Stars value={r.rating} /> <span className="text-muted">{r.author} about {r.about} · {r.depositId}</span></span>
                  {r.text && <span>{r.text}</span>}
                  {r.hidden && <span className="text-xs text-claim">Hidden: {r.hiddenReason}</span>}
                </span>
                {!r.hidden && <ConfirmAction label="Hide" confirmLabel="Hide review" danger reasonPlaceholder="Why (kept in the audit log)"
                  onConfirm={(reason) => hideReview(r.id, reason || "Breaks the review rules").then(load)} />}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
