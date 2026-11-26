"use client";
import Link from "next/link";
import { useState } from "react";
import { formatINR } from "@/lib/format";
import {
  AMENITY_LABEL, depositMonths, earlyAccessHoursLeft, Listing, photoTone, trustLine,
} from "@/lib/listings";
export function SafeImg({ src, alt, className = "", l }: { src: string; alt: string; className?: string; l: Listing }) { // safe img
  const [failed, setFailed] = useState(false);
  if (failed) return <NoPhoto l={l} className={className} />;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} className={`object-cover ${className}`} />;
}
export function ListingPhoto({ l, className = "" }: { l: Listing; className?: string }) { // listing photo
  const src = l.photos?.[0];
  if (src) return <SafeImg key={src} src={src} alt={`Photo of ${l.title}`} l={l} className={className} />;
  return <NoPhoto l={l} className={className} />;
}
function NoPhoto({ l, className = "" }: { l: Listing; className?: string }) {
  return (
    <div
      className={`grid place-items-center text-xs text-ink/60 ${className}`}
      style={{ backgroundColor: photoTone(l), backgroundImage: "repeating-linear-gradient(135deg, rgba(255,255,255,.35) 0 2px, transparent 2px 12px)" }}
      role="img"
      aria-label="No photo yet"
    >
      No photo yet
    </div>
  );
}
export function PremiumBadge({ small = false }: { small?: boolean }) { // premium badge
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full bg-[#F5E8CF] font-semibold text-[#7A4B00] ${small ? "px-1.5 py-0 text-[10px]" : "px-2 py-0.5 text-xs"}`}
      title="Verified Premium member: identity checked by TrustRent"
    >
      <svg width={small ? 10 : 12} height={small ? 10 : 12} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12 2l2.9 6.3 6.9.6-5.2 4.6 1.6 6.8L12 16.8 5.8 20.3l1.6-6.8L2.2 8.9l6.9-.6z" />
      </svg>
      Verified Premium
    </span>
  );
}
export function VerifiedLandlord() { // verified landlord
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-vault-soft px-2 py-0.5 text-xs font-medium text-vault">
      <svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 6.5 4.8 9 10 3" fill="none" stroke="currentColor" strokeWidth="2" /></svg>
      Verified owner
    </span>
  );
}
export function EarlyAccessTag({ l, premium }: { l: Listing; premium: boolean }) { // early access tag
  const hours = earlyAccessHoursLeft(l);
  if (!hours) return null;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${premium ? "bg-[#F5E8CF] text-[#7A4B00]" : "bg-ink text-white"}`}>
      {premium ? "New, you have early access" : `New, Premium only for ${hours}h`}
    </span>
  );
}
export function ListingCard({ l, premium }: { l: Listing; premium: boolean }) { // listing card
  const months = depositMonths(l);
  const trust = trustLine(l);
  const locked = !premium && earlyAccessHoursLeft(l) > 0;
  return (
    <article className="overflow-hidden rounded-2xl border border-line bg-surface transition-colors hover:border-ink/30">
      <Link href={`/listings/${l.id}`} className="grid gap-0 sm:grid-cols-[220px_minmax(0,1fr)]">
        <div className="relative">
          <ListingPhoto l={l} className="h-44 w-full sm:h-full sm:min-h-44" />
          {(l.photos?.length ?? 0) > 1 && (
            <span className="absolute right-2 bottom-2 rounded bg-black/60 px-1.5 py-0.5 text-[11px] text-white">{l.photos!.length} photos</span>
          )}
        </div>
        <div className="flex flex-col gap-2 p-4 sm:p-5">
          <div className="flex flex-wrap items-center gap-2">
            <EarlyAccessTag l={l} premium={premium} />
            <VerifiedLandlord />
          </div>
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h3 className="text-lg leading-snug">{l.title}</h3>
            <p className="tabular">
              <span className="font-display text-xl font-semibold">{formatINR(l.rent)}</span>
              <span className="text-sm text-muted">/month</span>
            </p>
          </div>
          <p className="text-sm text-muted">
            {l.locality}, {l.city} {l.pincode}, {l.bhk} BHK, {l.furnishing}{l.area_sqft ? `, ${l.area_sqft} sq ft` : ""}
          </p>
          <p className="text-sm">
            Deposit <span className="tabular font-medium">{formatINR(l.deposit)}</span>{" "}
            <span className={months > 2 ? "text-amber" : "text-muted"}>({months} month{months === 1 ? "" : "s"}{months > 2 ? ", above the 2-month cap" : ""})</span>
            <span className="text-muted">, stay {l.min_months} to {l.max_months} months</span>
          </p>
          <ul className="flex flex-wrap gap-1.5" aria-label="Facilities">
            {l.amenities.slice(0, 5).map((a) => (
              <li key={a} className="rounded-md bg-mist px-2 py-0.5 text-xs">{AMENITY_LABEL[a] ?? a}</li>
            ))}
            {l.amenities.length > 5 && <li className="px-1 text-xs text-muted">+{l.amenities.length - 5} more</li>}
          </ul>
          <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-1 text-sm">
            <span className={trust.tone === "good" ? "text-vault" : trust.tone === "warn" ? "text-amber" : "text-muted"}>{trust.text}</span>
            <span className="text-muted">Available {new Date(l.available_from).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</span>
          </div>
          {locked && <p className="text-xs text-muted">Premium members can contact this owner now; it opens to everyone soon.</p>}
        </div>
      </Link>
    </article>
  );
}
