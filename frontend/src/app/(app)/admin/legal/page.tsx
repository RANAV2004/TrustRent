"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ConfirmAction, Loading, PageHeader, Pill, when } from "@/components/admin-ui";
import {
  AdminLawyer, AdminLegalCase, banUser, Credentials, getLegalDesk, LawyerApplicationRow, openProtected,
  resetLawyerPassword, reviewLawyer, unbanUser,
} from "@/lib/admin";

type Tab = "applications" | "lawyers" | "cases";

function CredentialsBox({ name, c, onClose }: { name: string; c: Credentials; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const text = `TrustRent lawyer sign-in\nUsername: ${c.username}\nTemporary password: ${c.password}`;
  return (
    <div role="status" className="flex flex-col gap-2 rounded-2xl border border-vault/40 bg-vault-soft p-4 text-sm">
      <p className="font-medium text-vault">Account ready for {name}</p>
      <p className="font-mono">Username: {c.username}<br />Temporary password: {c.password}</p>
      <p className="text-muted">
        {c.emailed ? "These details were emailed to the lawyer." : "Email isn't set up on the server, so send these details to the lawyer yourself (phone or WhatsApp)."}
        {" "}They&apos;ll choose their own password at first sign-in. This password isn&apos;t shown again.
      </p>
      <div className="flex gap-2">
        <button type="button" onClick={() => navigator.clipboard?.writeText(text).then(() => setCopied(true))}
          className="rounded-md border border-vault px-3 py-1 text-xs text-vault">{copied ? "Copied" : "Copy details"}</button>
        <button type="button" onClick={onClose} className="px-2 text-xs text-muted">Done</button>
      </div>
    </div>
  );
}

function Doc({ label, path }: { label: string; path: string }) {
  const [err, setErr] = useState(false);
  return (
    <button type="button" onClick={() => openProtected(path).catch(() => setErr(true))} className="text-left text-sm text-vault hover:underline">
      {err ? "Couldn't open" : label}
    </button>
  );
}

function ApplicationRow({ a, onCredentials, reload }: { a: LawyerApplicationRow; onCredentials: (name: string, c: Credentials) => void; reload: () => void }) {
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function decide(approve: boolean) {
    setBusy(true);
    setError(null);
    try {
      const r = await reviewLawyer(a.reference, approve, note || undefined);
      if (r.credentials) onCredentials(a.fullName, r.credentials);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save the decision.");
    } finally {
      setBusy(false);
    }
  }
  const base = `/admin/legal/applications/${a.reference}`;
  const tone = a.status === "pending" ? "amber" : a.status === "approved" ? "green" : "red";
  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">{a.fullName} <span className="text-sm font-normal text-muted">{a.reference}</span></p>
          <p className="text-sm text-muted">{a.email}, {a.phone}</p>
        </div>
        <Pill tone={tone}>{a.status === "pending" ? "Waiting" : a.status === "approved" ? "Approved" : "Rejected"}</Pill>
      </div>
      <dl className="grid gap-1.5 text-sm sm:grid-cols-[150px_minmax(0,1fr)]">
        <dt className="text-muted">Enrolment</dt><dd><strong>{a.enrolmentNo}</strong>, {a.barCouncil}</dd>
        <dt className="text-muted">Practice</dt><dd>{a.city} · {a.experienceYears} years · {a.practiceAreas.join(", ")}</dd>
        {!!a.languages.length && (<><dt className="text-muted">Languages</dt><dd>{a.languages.join(", ")}</dd></>)}
        <dt className="text-muted">Office</dt><dd>{a.officeAddress}</dd>
        {a.about && (<><dt className="text-muted">About</dt><dd>{a.about}</dd></>)}
        <dt className="text-muted">Documents</dt>
        <dd className="flex flex-col">
          <Doc label="Photo" path={`${base}/photo`} />
          <Doc label={`${a.idDocType}: ${a.idFileName}`} path={`${base}/id`} />
          <Doc label={`Enrolment proof: ${a.enrolmentFileName}`} path={`${base}/enrolment`} />
        </dd>
        <dt className="text-muted">Submitted</dt><dd>{when(a.submittedAt, true)}{a.reviewedAt ? `, decided ${when(a.reviewedAt, true)}` : ""}</dd>
        {a.reviewNote && (<><dt className="text-muted">Reason</dt><dd>{a.reviewNote}</dd></>)}
      </dl>
      {a.status === "pending" && (
        <>
          <p className="text-xs text-muted">Check the enrolment number with the State Bar Council (website or phone) and that the name and photo match the ID before approving.</p>
          {rejecting ? (
            <div className="flex flex-col gap-2 sm:flex-row">
              <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Reason shown to the applicant"
                className="min-w-0 flex-1 rounded-lg border border-line px-3 py-1.5 text-sm" />
              <button type="button" disabled={busy} onClick={() => decide(false)} className="rounded-lg bg-claim px-3 py-1.5 text-sm text-white">Reject</button>
              <button type="button" onClick={() => setRejecting(false)} className="px-2 text-sm text-muted">Cancel</button>
            </div>
          ) : (
            <div className="flex gap-2">
              <button type="button" disabled={busy} onClick={() => decide(true)}
                className="rounded-lg bg-vault px-3 py-1.5 text-sm font-medium text-white hover:bg-vault-deep">{busy ? "Creating account..." : "Approve and create account"}</button>
              <button type="button" onClick={() => setRejecting(true)} className="rounded-lg border border-claim/40 px-3 py-1.5 text-sm text-claim hover:bg-claim-soft">Reject...</button>
            </div>
          )}
        </>
      )}
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
    </li>
  );
}

function LawyerRow({ l, onCredentials, reload }: { l: AdminLawyer; onCredentials: (name: string, c: Credentials) => void; reload: () => void }) {
  return (
    <tr className="border-t border-line align-top">
      <td className="py-3 pr-4">
        <p className="font-medium">{l.name}</p>
        <p className="text-xs text-muted">@{l.username} · {l.email} · {l.phone}</p>
        <p className="text-xs text-muted">{l.enrolmentNo}, {l.barCouncil}</p>
      </td>
      <td className="py-3 pr-4 text-sm">{l.city}<br /><span className="text-xs text-muted">{l.experienceYears} yrs</span></td>
      <td className="py-3 pr-4 text-sm tabular">{l.cases} / {l.agreements}</td>
      <td className="py-3 pr-4">
        {l.banned ? <Pill tone="red">Suspended</Pill> : l.passwordSet ? <Pill tone="green">Active</Pill> : <Pill tone="amber">Not signed in yet</Pill>}
        {l.banned?.reason && <p className="mt-1 text-xs text-muted">{l.banned.reason}</p>}
      </td>
      <td className="py-3">
        <div className="flex flex-col items-start gap-1.5">
          <ConfirmAction label="New password" confirmLabel="Issue new password"
            onConfirm={async () => { const r = await resetLawyerPassword(l.id); onCredentials(l.name, r.credentials); reload(); }} />
          {l.banned ? (
            <ConfirmAction label="Restore" confirmLabel="Restore to directory" onConfirm={async () => { await unbanUser(l.id); reload(); }} />
          ) : (
            <ConfirmAction label="Suspend" confirmLabel="Suspend" danger reasonPlaceholder="Reason (e.g. licence suspended)"
              onConfirm={async (reason) => { await banUser(l.id, reason); reload(); }} />
          )}
        </div>
      </td>
    </tr>
  );
}

export default function AdminLegal() { // admin legal
  const [data, setData] = useState<{ applications: LawyerApplicationRow[]; lawyers: AdminLawyer[]; cases: AdminLegalCase[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("applications");
  const [issued, setIssued] = useState<{ name: string; c: Credentials } | null>(null);
  const reload = useCallback(() => { getLegalDesk().then(setData, (e) => setError(e.message)); }, []);
  useEffect(() => { reload(); }, [reload]);
  const pending = data?.applications.filter((a) => a.status === "pending").length ?? 0;
  const apps = data ? [...data.applications].sort((a, b) => Number(b.status === "pending") - Number(a.status === "pending")) : [];
  const onCredentials = (name: string, c: Credentials) => { setIssued({ name, c }); window.scrollTo({ top: 0 }); };
  const tabs: [Tab, string][] = [
    ["applications", `Applications${pending ? ` (${pending} waiting)` : ""}`],
    ["lawyers", `Lawyers (${data?.lawyers.length ?? 0})`],
    ["cases", `Cases (${data?.cases.length ?? 0})`],
  ];
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Legal" intro="Verify lawyers, issue their sign-in details, and see owners' agreement requests. Lawyer documents are stored encrypted and open only here." />
      {issued && <CredentialsBox name={issued.name} c={issued.c} onClose={() => setIssued(null)} />}
      <div className="flex flex-wrap gap-2" role="tablist">
        {tabs.map(([t, label]) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`rounded-full border px-3 py-1 text-sm ${tab === t ? "border-vault bg-vault-soft text-vault" : "border-line bg-surface text-muted hover:text-ink"}`}>{label}</button>
        ))}
      </div>
      {!data ? <Loading error={error} /> : tab === "applications" ? (
        apps.length ? <ul className="grid gap-4 xl:grid-cols-2">{apps.map((a) => <ApplicationRow key={a.reference} a={a} onCredentials={onCredentials} reload={reload} />)}</ul>
          : <p className="text-sm text-muted">No lawyer applications yet. Lawyers apply from the sign-in page.</p>
      ) : tab === "lawyers" ? (
        data.lawyers.length ? (
          <div className="overflow-x-auto rounded-2xl border border-line bg-surface px-4">
            <table className="w-full min-w-[720px] text-left">
              <thead className="text-xs text-muted uppercase">
                <tr><th className="py-3 font-medium">Lawyer</th><th className="py-3 font-medium">City</th><th className="py-3 font-medium">Cases / docs</th><th className="py-3 font-medium">Status</th><th className="py-3 font-medium">Actions</th></tr>
              </thead>
              <tbody>{data.lawyers.map((l) => <LawyerRow key={l.id} l={l} onCredentials={onCredentials} reload={reload} />)}</tbody>
            </table>
          </div>
        ) : <p className="text-sm text-muted">No approved lawyers yet.</p>
      ) : (
        data.cases.length ? (
          <ul className="flex flex-col gap-2">
            {data.cases.map((c) => (
              <li key={c.id}>
                <Link href={`/legal/${c.id}`} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line bg-surface px-4 py-3 text-sm hover:border-ink/30">
                  <span><strong>{c.owner.name}</strong> with <strong>{c.lawyer.name}</strong> · <span className="text-muted">{c.subject}</span></span>
                  <span className="text-xs text-muted">{c.messages} messages · {c.agreements} documents · {when(c.updatedAt, true)}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : <p className="text-sm text-muted">No owner has contacted a lawyer yet.</p>
      )}
      {error && data && <p role="alert" className="text-sm text-claim">{error}</p>}
    </div>
  );
}
