"use client";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { apiMode } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useStore } from "@/lib/local-store";
import { getApplication, ID_DOCS, OwnerApplication, PROPERTY_DOCS, simulateReview, submitApplication } from "@/lib/owner";
const RELATIONS: { value: OwnerApplication["relation"]; label: string }[] = [
  { value: "owner", label: "I own it" },
  { value: "co-owner", label: "I own it with someone else" },
  { value: "authorised", label: "I'm authorised by the owner" },
];
function FileField({ label, hint, name, onPick }: { label: string; hint: string; name: string; onPick: (f: File | null) => void }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <input type="file" accept="image/*,application/pdf" onChange={(e) => onPick(e.target.files?.[0] ?? null)}
        className="rounded-lg border border-line px-3 py-2 file:mr-3 file:rounded-md file:border-0 file:bg-vault-soft file:px-2 file:py-1 file:text-vault" />
      <span className="text-xs text-muted">{name ? `Selected: ${name}` : hint}</span>
    </label>
  );
}
export default function VerifyOwner() { // owner verify
  const { user } = useAuth();
  const uidv = user?.id ?? "";
  const app = useStore(() => getApplication(uidv), [uidv]);
  const [editing, setEditing] = useState(false);
  const [relation, setRelation] = useState<OwnerApplication["relation"]>(app?.relation ?? "owner");
  const [idDocType, setIdDocType] = useState(app?.idDocType ?? "");
  const [idFile, setIdFile] = useState<File | null>(null);
  const [propertyDocType, setPropertyDocType] = useState(app?.propertyDocType ?? "");
  const [propertyFile, setPropertyFile] = useState<File | null>(null);
  const [propertyAddress, setPropertyAddress] = useState(app?.propertyAddress ?? "");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (!user) return null;
  const showForm = !app || app.status === "rejected" || editing;
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!idDocType || !idFile) return setError("Choose your ID document and upload a photo of it.");
    if (!propertyDocType || !propertyFile) return setError("Choose a property document and upload a photo of it.");
    if (propertyAddress.trim().length < 10) return setError("Enter the full address of the property.");
    if (!consent) return setError("Tick the declaration to continue.");
    setBusy(true);
    try {
      await submitApplication(
        { userId: user!.id, relation, idDocType, idFileName: idFile.name, propertyDocType, propertyFileName: propertyFile.name, propertyAddress: propertyAddress.trim() },
        { id: idFile, property: propertyFile },
      );
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't submit. Try again.");
    } finally {
      setBusy(false);
    }
  }
  async function review(approve: boolean) {
    setError(null);
    try {
      await simulateReview(user!.id, approve);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't update the application.");
    }
  }
  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <div>
        <Link href="/owner" className="text-sm text-muted hover:text-ink">Back to owner dashboard</Link>
        <h1 className="mt-2 text-3xl">Owner verification</h1>
        <p className="mt-1 text-muted">
          Before your home goes live, TrustRent checks that you are who you say you are and that you have the right to rent the property out.
          Tenants see a Verified owner badge on every listing you publish.
        </p>
      </div>
      {app && !showForm && (
        <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
          <p className="text-sm">
            Status:{" "}
            <strong className={app.status === "approved" ? "text-vault" : ""}>
              {app.status === "submitted" ? "Under review" : app.status === "approved" ? "Approved" : app.status}
            </strong>
          </p>
          <dl className="grid grid-cols-[140px_minmax(0,1fr)] gap-y-1.5 text-sm">
            <dt className="text-muted">ID document</dt><dd>{app.idDocType}, {app.idFileName}</dd>
            <dt className="text-muted">Property document</dt><dd>{app.propertyDocType}, {app.propertyFileName}</dd>
            <dt className="text-muted">Address</dt><dd>{app.propertyAddress}</dd>
            <dt className="text-muted">Submitted</dt><dd>{app.submittedAt ? new Date(app.submittedAt).toLocaleString("en-IN") : "-"}</dd>
          </dl>
          {app.status === "approved" ? (
            <Link href="/owner/listings/new" className="w-fit rounded-lg bg-vault px-4 py-2.5 text-sm font-medium text-white hover:bg-vault-deep">Add your home</Link>
          ) : (
            <button type="button" onClick={() => setEditing(true)} className="w-fit text-sm text-vault hover:underline">Replace documents</button>
          )}
        </section>
      )}
      {app?.status === "rejected" && !editing && (
        <p role="alert" className="rounded-lg bg-claim-soft px-4 py-3 text-sm text-claim">Not approved: {app.reviewNote}</p>
      )}
      {showForm && (
        <form onSubmit={submit} noValidate className="flex flex-col gap-5 rounded-2xl border border-line bg-surface p-6">
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium">Your relation to the property</legend>
            {RELATIONS.map((r) => (
              <label key={r.value} className="flex items-center gap-2 text-sm">
                <input type="radio" name="relation" checked={relation === r.value} onChange={() => setRelation(r.value)} className="accent-vault" />
                {r.label}
              </label>
            ))}
          </fieldset>
          <div className="flex flex-col gap-3 border-t border-line pt-4">
            <h2 className="text-base">1. Your identity</h2>
            <select aria-label="ID document type" value={idDocType} onChange={(e) => setIdDocType(e.target.value)} className="rounded-lg border border-line px-3 py-2.5 text-sm">
              <option value="">Choose an ID document</option>
              {ID_DOCS.map((d) => <option key={d}>{d}</option>)}
            </select>
            <FileField label="Photo or scan of the ID" name={idFile?.name ?? ""} onPick={setIdFile}
              hint="For Aadhaar, use the masked version from the UIDAI website (only the last 4 digits visible)." />
          </div>
          <div className="flex flex-col gap-3 border-t border-line pt-4">
            <h2 className="text-base">2. Proof you can rent the property</h2>
            <select aria-label="Property document type" value={propertyDocType} onChange={(e) => setPropertyDocType(e.target.value)} className="rounded-lg border border-line px-3 py-2.5 text-sm">
              <option value="">Choose a property document</option>
              {PROPERTY_DOCS.map((d) => <option key={d}>{d}</option>)}
            </select>
            <FileField label="Photo or scan of the document" name={propertyFile?.name ?? ""} onPick={setPropertyFile}
              hint="The owner's name and the property address must be readable." />
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium">Property address</span>
              <textarea rows={2} value={propertyAddress} onChange={(e) => setPropertyAddress(e.target.value)}
                placeholder="Flat 302, Shanti Residency, Scheme 54, Vijay Nagar, Indore 452010" className="rounded-lg border border-line px-3 py-2.5" />
            </label>
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1 h-4 w-4 accent-vault" />
            I declare these documents are genuine. TrustRent may use them only to verify me and this property.
          </label>
          <p className="text-xs text-muted">{apiMode
            ? "Documents are stored encrypted (AES-256-GCM) and seen only by the TrustRent review team."
            : "Demo: documents are not uploaded or stored; only the file names are saved."}</p>
          {error && <p role="alert" className="text-sm text-claim">{error}</p>}
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className="rounded-lg bg-vault px-5 py-2.5 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">{busy ? "Uploading..." : "Submit for review"}</button>
            {editing && <button type="button" onClick={() => setEditing(false)} className="px-3 text-sm text-muted hover:text-ink">Cancel</button>}
          </div>
        </form>
      )}
      {app?.status === "submitted" && !editing && (
        <aside className="flex flex-col gap-2 rounded-2xl border border-dashed border-amber/60 p-5">
          <p className="text-sm font-medium">Demo: TrustRent review desk</p>
          <p className="text-xs text-muted">In the real app a reviewer (arbitrator account) approves applications. Use these buttons to try both outcomes{apiMode ? " (backend DEMO_MODE only)" : ""}.</p>
          <div className="flex gap-2">
            <button type="button" onClick={() => review(true)} className="rounded-lg bg-vault px-3 py-1.5 text-sm text-white hover:bg-vault-deep">Approve</button>
            <button type="button" onClick={() => review(false)} className="rounded-lg border border-claim/40 px-3 py-1.5 text-sm text-claim hover:bg-claim-soft">Reject</button>
          </div>
        </aside>
      )}
    </div>
  );
}
