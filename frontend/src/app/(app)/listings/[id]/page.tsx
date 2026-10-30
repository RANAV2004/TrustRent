"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, use, useState } from "react";
import { EarlyAccessTag, ListingPhoto, SafeImg, VerifiedLandlord } from "@/components/listing-ui";
import { PayDepositCard } from "@/components/pay-deposit";
import { apiMode } from "@/lib/api";
import { isPremium } from "@/lib/auth";
import { useAuth } from "@/lib/auth-context";
import { formatINR } from "@/lib/format";
import {
  AMENITY_LABEL, depositMonths, earlyAccessHoursLeft, getListing, mapEmbedUrl, mapsLink, TENANT_LABEL, trustLine,
} from "@/lib/listings";
import { useStore } from "@/lib/local-store";
import { apiReady } from "@/lib/sync";
import { hasConfirmedVisit, openConversation, requestVisit, sendText } from "@/lib/messages";
function defaultSlot(daysAhead: number, hour: number) {
  const d = new Date();
  d.setDate(d.getDate() + daysAhead);
  d.setHours(hour, 0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(hour)}:00`;
}
export default function ListingPage({ params }: { params: Promise<{ id: string }> }) { // listing
  const { id } = use(params);
  const { user } = useAuth();
  const router = useRouter();
  const l = useStore(() => getListing(id), [id]);
  const visitConfirmed = useStore(() => (user ? hasConfirmedVisit(id, user.id) : false), [id, user?.id]);
  const [mode, setMode] = useState<"none" | "message" | "visit">("none");
  const [text, setText] = useState("");
  const [slots, setSlots] = useState([defaultSlot(1, 11), defaultSlot(2, 17), ""]);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [photo, setPhoto] = useState(0);
  const [sending, setSending] = useState(false);
  const ready = useStore(apiReady, []);
  if (!l && !ready) {
    return <p className="text-sm text-muted" role="status">Loading...</p>;
  }
  if (!l) {
    return (
      <div className="flex flex-col items-start gap-3">
        <h1 className="text-2xl">This listing isn&apos;t available</h1>
        <p className="text-muted">It may have been rented out or removed by the owner.</p>
        <Link href="/search" className="text-vault hover:underline">Back to search</Link>
      </div>
    );
  }
  const premium = isPremium(user);
  const hoursLeft = earlyAccessHoursLeft(l);
  const locked = hoursLeft > 0 && !premium;
  const mine = !!user && l.owner_id === user.id;
  const months = depositMonths(l);
  const trust = trustLine(l);
  const photos = l.photos ?? [];
  const exact = !!l.show_exact_location || mine || visitConfirmed;
  async function send(e: FormEvent) {
    e.preventDefault();
    if (!user || sending) return;
    setError(null);
    const chosen = slots.filter(Boolean);
    if (mode === "message") {
      if (text.trim().length < 2) return setError("Write a short message to the owner.");
    } else {
      if (!chosen.length) return setError("Pick at least one time that suits you.");
      if (chosen.some((s) => new Date(s).getTime() < Date.now())) return setError("Visit times must be in the future.");
    }
    setSending(true);
    try {
      const c = await openConversation(l!, user);
      if (mode === "message") await sendText(c, user, text);
      else await requestVisit(c, user, chosen.map((s) => new Date(s).toISOString()), note);
      router.push(`/messages?c=${c.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send. Try again.");
      setSending(false);
    }
  }
  return (
    <div className="flex flex-col gap-6">
      <Link href="/search" className="w-fit text-sm text-muted hover:text-ink">Back to results</Link>
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <EarlyAccessTag l={l} premium={premium} />
          <VerifiedLandlord />
          <span className="text-xs text-muted">Ref {l.id}</span>
        </div>
        <h1 className="text-3xl sm:text-4xl">{l.title}</h1>
        <p className="text-muted">{l.address ? `${l.address}, ` : ""}{l.locality}, {l.city} {l.pincode}</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex min-w-0 flex-col gap-6">
          <section aria-label="Photos" className="flex flex-col gap-2">
            {photos.length ? (
              <>
                <SafeImg key={photos[photo]} src={photos[photo]} l={l} alt={`Photo ${photo + 1} of ${photos.length}`} className="aspect-[16/10] w-full rounded-2xl" />
                {photos.length > 1 && (
                  <div className="flex gap-2 overflow-x-auto">
                    {photos.map((p, i) => (
                      <button key={i} type="button" onClick={() => setPhoto(i)} aria-label={`Show photo ${i + 1}`} className={`shrink-0 overflow-hidden rounded-lg border-2 ${i === photo ? "border-vault" : "border-transparent"}`}>
                        <SafeImg src={p} l={l} alt="" className="h-16 w-24" />
                      </button>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <ListingPhoto l={l} className="aspect-[16/10] w-full rounded-2xl" />
            )}
          </section>
          <section className="rounded-2xl border border-line bg-surface p-5">
            <h2 className="mb-3 text-lg">About this home</h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
              <div><dt className="text-muted">Size</dt><dd className="font-medium">{l.bhk} BHK{l.area_sqft ? `, ${l.area_sqft} sq ft` : ""}</dd></div>
              <div><dt className="text-muted">Furnishing</dt><dd className="font-medium capitalize">{l.furnishing}</dd></div>
              <div><dt className="text-muted">Available from</dt><dd className="font-medium">{new Date(l.available_from).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</dd></div>
              <div><dt className="text-muted">Stay</dt><dd className="font-medium">{l.min_months} to {l.max_months} months</dd></div>
              <div><dt className="text-muted">Open to</dt><dd className="font-medium">{l.preferred_tenants.map((t) => TENANT_LABEL[t]).join(", ")}</dd></div>
              <div><dt className="text-muted">Listed</dt><dd className="font-medium">{l.listed_at ? new Date(l.listed_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : "NA"}</dd></div>
            </dl>
            {l.description && <p className="mt-4 text-[15px] whitespace-pre-line">{l.description}</p>}
          </section>
          <section className="rounded-2xl border border-line bg-surface p-5">
            <h2 className="mb-3 text-lg">Facilities</h2>
            <ul className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
              {Object.entries(AMENITY_LABEL).map(([k, label]) => {
                const has = l.amenities.includes(k);
                return (
                  <li key={k} className={`flex items-center gap-2 ${has ? "" : "text-muted line-through decoration-1"}`}>
                    <span aria-hidden="true" className={has ? "text-vault" : "text-muted"}>{has ? "Yes" : "No"}</span>
                    <span>{label}</span>
                    <span className="sr-only">{has ? "available" : "not available"}</span>
                  </li>
                );
              })}
            </ul>
          </section>
          <section className="rounded-2xl border border-line bg-surface p-5">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-lg">Location</h2>
              <a href={mapsLink(l, exact)} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-vault hover:underline">Open in Google Maps</a>
            </div>
            <iframe
              title={`Map of ${l.locality}, ${l.city}`}
              src={mapEmbedUrl(l, exact)}
              className="h-72 w-full rounded-xl border border-line"
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
            />
            {exact && l.address && <p className="mt-2 text-sm">{l.address}, {l.locality}, {l.city} {l.pincode}</p>}
            {!exact && (
              <p className="mt-2 text-xs text-muted">The map shows the area. The exact location appears here once the owner confirms your visit.</p>
            )}
            {mine && !l.show_exact_location && <p className="mt-2 text-xs text-muted">You see the exact pin because this is your listing. Tenants see the area until you confirm their visit.</p>}
          </section>
          <section className="rounded-2xl border border-line bg-surface p-5">
            <h2 className="mb-3 text-lg">About the owner</h2>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{l.owner_name ?? l.landlord.name}</span>
              <VerifiedLandlord />
            </div>
            <p className={`mt-1 text-sm ${trust.tone === "good" ? "text-vault" : trust.tone === "warn" ? "text-amber" : "text-muted"}`}>{trust.text}</p>
            {l.landlord.disputes_lost > 0 && <p className="text-sm text-amber">Lost {l.landlord.disputes_lost} deposit dispute{l.landlord.disputes_lost > 1 ? "s" : ""} on TrustRent</p>}
            {l.about_owner && <p className="mt-3 text-[15px] whitespace-pre-line">{l.about_owner}</p>}
          </section>
        </div>
        <aside className="flex flex-col gap-4 lg:sticky lg:top-24 lg:self-start">
          <section className="rounded-2xl border border-line bg-surface p-5">
            <p className="tabular"><span className="font-display text-3xl font-semibold">{formatINR(l.rent)}</span><span className="text-muted">/month</span></p>
            <p className="mt-1 text-sm">
              Deposit {formatINR(l.deposit)}{" "}
              <span className={months > 2 ? "text-amber" : "text-muted"}>({months} month{months === 1 ? "" : "s"})</span>
            </p>
            {months > 2 && <p className="mt-1 text-xs text-amber">Above the 2-month cap in the Model Tenancy Act, 2021. You can negotiate this.</p>}
            <p className="mt-3 rounded-lg bg-vault-soft px-3 py-2 text-xs text-vault">Your deposit is paid to TrustRent, not the owner, and receipted on the blockchain.</p>
            <div className="mt-4 flex flex-col gap-2">
              {mine ? (
                <Link href="/owner" className="rounded-lg border border-line px-4 py-2.5 text-center text-sm font-medium">Manage your listing</Link>
              ) : locked ? (
                <div className="flex flex-col gap-2 rounded-xl border border-[#E8D3A8] bg-[#FBF4E6] p-4">
                  <p className="text-sm font-semibold text-[#7A4B00]">New listing: Premium early access</p>
                  <p className="text-sm text-[#5C4310]">Premium members can contact this owner now. Everyone else can in {hoursLeft} hour{hoursLeft === 1 ? "" : "s"}.</p>
                  <Link href={`/premium?from=${l.id}`} className="mt-1 rounded-lg bg-[#7A4B00] px-4 py-2.5 text-center text-sm font-medium text-white hover:bg-[#5C3800]">Get early access</Link>
                </div>
              ) : (
                <>
                  <button type="button" onClick={() => setMode("message")} className="rounded-lg bg-vault px-4 py-2.5 text-sm font-medium text-white hover:bg-vault-deep">Message owner</button>
                  <button type="button" onClick={() => setMode("visit")} className="rounded-lg border border-line px-4 py-2.5 text-sm font-medium hover:border-ink/40">Request a visit</button>
                </>
              )}
            </div>
            {mode !== "none" && !locked && !mine && (
              <form onSubmit={send} className="mt-4 flex flex-col gap-3 border-t border-line pt-4">
                {mode === "message" ? (
                  <label className="flex flex-col gap-1.5 text-sm">
                    <span className="font-medium">Message to {l.owner_name ?? l.landlord.name}</span>
                    <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} placeholder="Hi, is the flat still available? We're a family of three, looking to move in next month." className="rounded-lg border border-line px-3 py-2" />
                  </label>
                ) : (
                  <>
                    <p className="text-sm font-medium">Suggest up to 3 times to see the home</p>
                    {slots.map((s, i) => (
                      <label key={i} className="flex flex-col gap-1 text-sm">
                        <span className="text-xs text-muted">Option {i + 1}{i === 2 ? " (optional)" : ""}</span>
                        <input type="datetime-local" value={s} onChange={(e) => setSlots(slots.map((x, j) => (j === i ? e.target.value : x)))} className="rounded-lg border border-line px-3 py-2" />
                      </label>
                    ))}
                    <label className="flex flex-col gap-1 text-sm">
                      <span className="text-xs text-muted">Note (optional)</span>
                      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="I'll come with my parents" className="rounded-lg border border-line px-3 py-2" />
                    </label>
                  </>
                )}
                {error && <p role="alert" className="text-sm text-claim">{error}</p>}
                <div className="flex gap-2">
                  <button type="submit" className="flex-1 rounded-lg bg-vault px-4 py-2.5 text-sm font-medium text-white hover:bg-vault-deep">{mode === "message" ? "Send message" : "Send visit request"}</button>
                  <button type="button" onClick={() => setMode("none")} className="rounded-lg px-3 text-sm text-muted hover:text-ink">Cancel</button>
                </div>
              </form>
            )}
          </section>
          {apiMode && !mine && visitConfirmed && <PayDepositCard l={l} />}
        </aside>
      </div>
    </div>
  );
}
