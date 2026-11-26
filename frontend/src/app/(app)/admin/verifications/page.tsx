"use client";
import { useCallback, useEffect, useState } from "react";
import { Loading, PageHeader } from "@/components/admin-ui";
import { getVerifications, IdRequest, openProtected, OwnerRequest, reviewIdentity, reviewOwner } from "@/lib/admin";
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "");
const pill: Record<string, string> = {
  submitted: "bg-amber-soft text-amber", pending: "bg-amber-soft text-amber",
  approved: "bg-vault-soft text-vault", rejected: "bg-claim-soft text-claim",
};
const pillText: Record<string, string> = { submitted: "Pending", pending: "Pending", approved: "Verified", rejected: "Rejected" };
function Decide({ onDecide }: { onDecide: (approve: boolean, note?: string) => Promise<void> }) {
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const run = (approve: boolean) => { setBusy(true); onDecide(approve, note || undefined).finally(() => setBusy(false)); };
  return rejecting ? (
    <div className="flex flex-col gap-2 sm:flex-row">
      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Reason shown to the user" className="min-w-0 flex-1 rounded-lg border border-line px-3 py-1.5 text-sm" />
      <button type="button" disabled={busy} onClick={() => run(false)} className="rounded-lg bg-claim px-3 py-1.5 text-sm text-white">Reject</button>
      <button type="button" onClick={() => setRejecting(false)} className="px-2 text-sm text-muted">Cancel</button>
    </div>
  ) : (
    <div className="flex gap-2">
      <button type="button" disabled={busy} onClick={() => run(true)} className="rounded-lg bg-vault px-3 py-1.5 text-sm font-medium text-white hover:bg-vault-deep">Approve</button>
      <button type="button" onClick={() => setRejecting(true)} className="rounded-lg border border-claim/40 px-3 py-1.5 text-sm text-claim hover:bg-claim-soft">Reject...</button>
    </div>
  );
}
function DocLink({ label, path }: { label: string; path: string }) {
  const [err, setErr] = useState(false);
  return (
    <button type="button" onClick={() => openProtected(path).catch(() => setErr(true))} className="text-left text-sm text-vault hover:underline">
      {err ? "Couldn't open" : label}
    </button>
  );
}
function OwnerRow({ r, reload }: { r: OwnerRequest; reload: () => void }) {
  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">{r.applicant.name} <span className="text-sm font-normal text-muted">@{r.applicant.username}</span></p>
          <p className="text-sm text-muted">{r.applicant.email}, {r.applicant.phone}</p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${pill[r.status]}`}>{pillText[r.status]}</span>
      </div>
      <dl className="grid gap-2 text-sm sm:grid-cols-[140px_minmax(0,1fr)]">
        <dt className="text-muted">Property</dt><dd>{r.propertyAddress} ({r.relation})</dd>
        <dt className="text-muted">ID document</dt><dd><DocLink label={`${r.idDocType}: ${r.idFileName}`} path={`/admin/owner-applications/${r.userId}/id`} /></dd>
        <dt className="text-muted">Property document</dt><dd><DocLink label={`${r.propertyDocType}: ${r.propertyFileName}`} path={`/admin/owner-applications/${r.userId}/property`} /></dd>
        <dt className="text-muted">Submitted</dt><dd>{when(r.submittedAt)}{r.reviewedAt ? `, reviewed ${when(r.reviewedAt)}` : ""}</dd>
        {r.reviewNote && (<><dt className="text-muted">Note</dt><dd>{r.reviewNote}</dd></>)}
      </dl>
      {r.status === "submitted" && <Decide onDecide={async (a, n) => { await reviewOwner(r.userId, a, n); reload(); }} />}
    </li>
  );
}
function IdRow({ r, reload }: { r: IdRequest; reload: () => void }) {
  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">{r.applicant.name} <span className="text-sm font-normal text-muted">@{r.applicant.username}</span></p>
          <p className="text-sm text-muted">{r.applicant.email}, {r.applicant.phone}</p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${pill[r.status]}`}>{pillText[r.status]}</span>
      </div>
      <p className="text-sm"><DocLink label={`${r.docType}: ${r.fileName}`} path={`/admin/identity/${r.id}/file`} /> <span className="text-muted">sent {when(r.submittedAt)}</span></p>
      {r.reviewNote && <p className="text-sm text-muted">Note: {r.reviewNote}</p>}
      {r.status === "pending" && <Decide onDecide={async (a, n) => { await reviewIdentity(r.id, a, n); reload(); }} />}
    </li>
  );
}
export default function VerificationsPage() { // admin verify
  const [data, setData] = useState<{ owners: OwnerRequest[]; identities: IdRequest[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => { getVerifications().then(setData, (e) => setError(e.message)); }, []);
  useEffect(() => { reload(); }, [reload]);
  return (
    <div>
      <PageHeader title="Verifications" intro="Owner and ID documents waiting for a decision. Documents are stored encrypted and open only here. Every submission and decision updates the Excel register.">
        <button type="button" onClick={() => openProtected("/admin/verification-register.xlsx", "TrustRent_verification_register.xlsx").catch((e) => setError(e.message))}
          className="rounded-lg border border-line bg-surface px-4 py-2 text-sm hover:border-ink/40">Download Excel register</button>
      </PageHeader>
      {!data ? <Loading error={error} /> : (
        <div className="grid gap-6 xl:grid-cols-2">
          <section className="flex flex-col gap-3">
            <h2 className="text-lg">Owner verification <span className="text-muted">({data.owners.length})</span></h2>
            {data.owners.length ? <ul className="flex flex-col gap-3">{data.owners.map((r) => <OwnerRow key={r.userId} r={r} reload={reload} />)}</ul>
              : <p className="text-sm text-muted">No owner applications yet.</p>}
          </section>
          <section className="flex flex-col gap-3">
            <h2 className="text-lg">ID verification <span className="text-muted">({data.identities.length})</span></h2>
            {data.identities.length ? <ul className="flex flex-col gap-3">{data.identities.map((r) => <IdRow key={r.id} r={r} reload={reload} />)}</ul>
              : <p className="text-sm text-muted">No ID submissions yet.</p>}
          </section>
        </div>
      )}
      {error && data && <p role="alert" className="mt-4 text-sm text-claim">{error}</p>}
    </div>
  );
}
