"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { ApiError, apiMode } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { CaseSummary, getCases, getLawyers, LawyerCard, openCase, PRACTICE_AREAS } from "@/lib/legal";
import { useStore } from "@/lib/local-store";
import { ownerListingsFor } from "@/lib/owner";

function Avatar({ l }: { l: LawyerCard }) {
  const [failed, setFailed] = useState(false);
  const initials = l.name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  if (!l.photo || failed) {
    return <span className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-vault-soft text-lg font-semibold text-vault" aria-hidden="true">{initials}</span>;
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={l.photo} alt={`Photo of ${l.name}`} onError={() => setFailed(true)} className="h-16 w-16 shrink-0 rounded-full object-cover" />;
}

function Hire({ lawyer, listings, onClose }: { lawyer: LawyerCard; listings: { id: string; title: string }[]; onClose: () => void }) {
  const router = useRouter();
  const [listingId, setListingId] = useState(listings[0]?.id ?? "");
  const [message, setMessage] = useState(
    "Hello, I'd like you to prepare a rental agreement for my home. Please let me know what details and documents you need and your fee.",
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!message.trim()) return setError("Write a message.");
    setBusy(true);
    setError(null);
    try {
      const c = await openCase(lawyer.id, listingId || null, message.trim());
      router.push(`/legal/${c.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't send. Try again.");
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-3 border-t border-line pt-3">
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Which home is it for?</span>
        <select value={listingId} onChange={(e) => setListingId(e.target.value)} className="rounded-lg border border-line bg-surface px-3 py-2">
          {listings.map((x) => <option key={x.id} value={x.id}>{x.title}</option>)}
          <option value="">Another property / not listed on TrustRent</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Message</span>
        <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={4} maxLength={2000}
          className="rounded-lg border border-line bg-surface px-3 py-2" />
      </label>
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">
          {busy ? "Sending..." : `Message ${lawyer.name.split(" ")[0]}`}
        </button>
        <button type="button" onClick={onClose} className="px-2 text-sm text-muted">Cancel</button>
      </div>
    </form>
  );
}

export default function OwnerLawyers() { // owner lawyers
  const { user } = useAuth();
  const uid = user?.id ?? "";
  const myListings = useStore(() => ownerListingsFor(uid), [uid]);
  const listings = useMemo(() => myListings.map((l) => ({ id: l.id, title: l.title })), [myListings]);
  const [lawyers, setLawyers] = useState<LawyerCard[] | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [area, setArea] = useState("");
  const [hiring, setHiring] = useState<string | null>(null);
  useEffect(() => {
    if (!apiMode) return;
    getLawyers().then(setLawyers, (e) => setError(e.message));
    getCases().then(setCases, () => {});
  }, []);
  const shown = useMemo(() => {
    const term = q.trim().toLowerCase();
    return (lawyers ?? []).filter((l) =>
      (!area || l.practiceAreas.includes(area)) &&
      (!term || [l.name, l.city, l.languages.join(" "), l.officeAddress].join(" ").toLowerCase().includes(term)));
  }, [lawyers, q, area]);
  if (!apiMode) {
    return <p className="text-sm text-muted">The lawyer directory needs the TrustRent server. It isn&apos;t available in this demo.</p>;
  }
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl">Lawyers</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Hire a verified lawyer to prepare the rental agreement between you and your tenant. The lawyer sends the agreement here as a PDF: download it, print it, and share it with your tenant.
        </p>
      </div>
      {!!cases.length && (
        <section className="flex flex-col gap-3">
          <h2 className="text-lg">Your requests</h2>
          <ul className="grid gap-3 md:grid-cols-2">
            {cases.map((c) => (
              <li key={c.id}>
                <Link href={`/legal/${c.id}`} className="flex flex-col gap-0.5 rounded-xl border border-line bg-surface p-4 hover:border-ink/30">
                  <span className="flex items-center gap-2 font-medium">
                    {c.lawyer.name}
                    {c.unread > 0 && <span className="rounded-full bg-vault px-2 py-0.5 text-[11px] font-semibold text-white">{c.unread} new</span>}
                  </span>
                  <span className="text-sm text-muted">{c.listing?.title ?? c.subject}</span>
                  <span className="truncate text-sm">{c.lastMessage}</span>
                  <span className="text-xs text-muted">{c.agreements} document{c.agreements === 1 ? "" : "s"}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-lg">Verified lawyers</h2>
          <div className="flex flex-wrap gap-2">
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="City, name or language" aria-label="Search lawyers"
              className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm sm:w-60" />
            <select value={area} onChange={(e) => setArea(e.target.value)} aria-label="Practice area"
              className="rounded-lg border border-line bg-surface px-3 py-2 text-sm">
              <option value="">All practice areas</option>
              {PRACTICE_AREAS.map((a) => <option key={a}>{a}</option>)}
            </select>
          </div>
        </div>
        {error && <p role="alert" className="text-sm text-claim">{error}</p>}
        {!lawyers ? !error && <p className="text-sm text-muted">Loading...</p> : !shown.length ? (
          <p className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">
            {lawyers.length ? "No lawyers match your search." : "No lawyers are listed yet. Check back soon."}
          </p>
        ) : (
          <ul className="grid gap-4 lg:grid-cols-2">
            {shown.map((l) => (
              <li key={l.id} className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
                <div className="flex gap-4">
                  <Avatar l={l} />
                  <div className="min-w-0">
                    <p className="text-lg font-medium">{l.name}</p>
                    <p className="text-sm text-muted">{l.city} · {l.experienceYears} year{l.experienceYears === 1 ? "" : "s"} of practice</p>
                    <p className="text-xs text-muted">{l.barCouncil}, enrolment {l.enrolmentNo}</p>
                  </div>
                </div>
                <ul className="flex flex-wrap gap-1.5">
                  {l.practiceAreas.map((a) => <li key={a} className="rounded-full bg-mist px-2.5 py-0.5 text-xs">{a}</li>)}
                </ul>
                <dl className="grid gap-1 text-sm sm:grid-cols-[90px_minmax(0,1fr)]">
                  {!!l.languages.length && (<><dt className="text-muted">Languages</dt><dd>{l.languages.join(", ")}</dd></>)}
                  <dt className="text-muted">Phone</dt><dd><a href={`tel:${l.phone}`} className="text-vault hover:underline">{l.phone}</a></dd>
                  <dt className="text-muted">Email</dt><dd className="break-all"><a href={`mailto:${l.email}`} className="text-vault hover:underline">{l.email}</a></dd>
                  <dt className="text-muted">Office</dt><dd>{l.officeAddress}</dd>
                </dl>
                {l.about && <p className="text-sm">{l.about}</p>}
                {hiring === l.id ? (
                  <Hire lawyer={l} listings={listings} onClose={() => setHiring(null)} />
                ) : (
                  <button type="button" onClick={() => setHiring(l.id)}
                    className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep">
                    Hire for an agreement
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-muted">
          TrustRent verifies each lawyer&apos;s identity and Bar Council enrolment but doesn&apos;t recommend any lawyer. Listings are information only. You agree the work and fee directly with the lawyer: TrustRent takes no commission.
        </p>
      </section>
    </div>
  );
}
