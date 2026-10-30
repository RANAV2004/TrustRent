"use client";
import Link from "next/link";
import { useState } from "react";
import { ListingPhoto } from "@/components/listing-ui";
import { useAuth } from "@/lib/auth-context";
import { formatINR } from "@/lib/format";
import { earlyAccessHoursLeft } from "@/lib/listings";
import { useStore } from "@/lib/local-store";
import { conversationsFor, messagesIn, unreadCount } from "@/lib/messages";
import { deleteOwnerListing, getApplication, ownerListingsFor, setListingStatus } from "@/lib/owner";
function VerificationCard({ status, note }: { status: string; note?: string }) {
  const copy: Record<string, { title: string; body: string; cta?: string; tone: string }> = {
    not_started: {
      title: "Verify yourself to list a home",
      body: "Upload one ID document and one property document. The TrustRent team checks them, usually within a day, and then you can publish listings with a Verified owner badge.",
      cta: "Start verification",
      tone: "border-amber/40 bg-amber-soft",
    },
    submitted: {
      title: "Your application is under review",
      body: "We're checking your documents. You'll be able to publish listings as soon as you're approved.",
      cta: "View application",
      tone: "border-line bg-surface",
    },
    approved: {
      title: "You're a verified owner",
      body: "Your listings carry the Verified owner badge, and tenants can see your TrustRent record.",
      tone: "border-vault/30 bg-vault-soft",
    },
    rejected: {
      title: "We couldn't verify your documents",
      body: note ?? "Please upload clearer documents and apply again.",
      cta: "Fix and resubmit",
      tone: "border-claim/30 bg-claim-soft",
    },
  };
  const c = copy[status];
  return (
    <section className={`flex flex-col gap-2 rounded-2xl border p-5 sm:flex-row sm:items-center sm:justify-between ${c.tone}`}>
      <div>
        <h2 className="text-lg">{c.title}</h2>
        <p className="max-w-2xl text-sm text-muted">{c.body}</p>
      </div>
      {c.cta && (
        <Link href="/owner/verify" className="shrink-0 rounded-lg bg-vault px-4 py-2.5 text-center text-sm font-medium text-white hover:bg-vault-deep">
          {c.cta}
        </Link>
      )}
    </section>
  );
}
export default function OwnerDashboard() { // owner dashboard
  const { user } = useAuth();
  const uidv = user?.id ?? "";
  const [actionError, setActionError] = useState<string | null>(null);
  const app = useStore(() => getApplication(uidv), [uidv]);
  const listings = useStore(() => ownerListingsFor(uidv), [uidv]);
  const convs = useStore(() => conversationsFor(uidv), [uidv]);
  const unread = useStore(() => unreadCount(uidv), [uidv]);
  const pendingVisits = useStore(
    () => conversationsFor(uidv).flatMap((c) => messagesIn(c.id)).filter((m) => m.kind === "visit" && m.visit?.status === "pending" && m.senderId !== uidv).length,
    [uidv],
  );
  if (!user) return null;
  const status = app?.status ?? "not_started";
  function act(fn: () => Promise<unknown>) {
    setActionError(null);
    fn().catch((err) => setActionError(err instanceof Error ? err.message : "Couldn't update the listing."));
  }
  const approved = status === "approved";
  const stats = [
    { label: "Live listings", value: listings.filter((l) => l.status !== "paused").length },
    { label: "Conversations", value: convs.length },
    { label: "Unread", value: unread },
    { label: "Visit requests", value: pendingVisits },
  ];
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted">Owner dashboard</p>
          <h1 className="text-3xl sm:text-4xl">Hello, {user.firstName}</h1>
        </div>
        {approved && (
          <Link href="/owner/listings/new" className="rounded-lg bg-vault px-4 py-2.5 text-sm font-medium text-white hover:bg-vault-deep">
            Add a listing
          </Link>
        )}
      </div>
      <VerificationCard status={status} note={app?.reviewNote} />
      <section className="grid grid-cols-2 gap-3 md:grid-cols-4" aria-label="Summary">
        {stats.map((s) => (
          <div key={s.label} className="rounded-2xl border border-line bg-surface p-4">
            <p className="text-sm text-muted">{s.label}</p>
            <p className="font-display text-3xl font-semibold tabular">{s.value}</p>
          </div>
        ))}
      </section>
      {(unread > 0 || pendingVisits > 0) && (
        <Link href="/messages" className="-mt-4 w-fit text-sm text-vault hover:underline">
          Open messages{pendingVisits ? `, ${pendingVisits} visit request${pendingVisits === 1 ? "" : "s"} waiting` : ""}
        </Link>
      )}
      <section className="flex flex-col gap-3">
        <h2 className="text-xl">My listings</h2>
        {actionError && <p role="alert" className="text-sm text-claim">{actionError}</p>}
        {listings.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">
            {approved ? (
              <>No listings yet. <Link href="/owner/listings/new" className="text-vault hover:underline">Add your first home</Link>.</>
            ) : (
              "Once you're verified you can add your home here."
            )}
          </div>
        ) : (
          <ul className="flex flex-col gap-3">
            {listings.map((l) => {
              const early = earlyAccessHoursLeft(l);
              return (
                <li key={l.id} className="grid overflow-hidden rounded-2xl border border-line bg-surface sm:grid-cols-[160px_minmax(0,1fr)]">
                  <ListingPhoto l={l} className="h-32 w-full sm:h-full" />
                  <div className="flex flex-col gap-2 p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${l.status === "blocked" ? "bg-claim-soft text-claim" : l.status === "paused" ? "bg-mist text-muted" : "bg-vault-soft text-vault"}`}>
                        {l.status === "blocked" ? "Unlisted by TrustRent" : l.status === "paused" ? "Paused" : "Live"}
                      </span>
                      {early > 0 && l.status === "live" && <span className="text-xs text-muted">Premium-only for {early}h more</span>}
                      <span className="text-xs text-muted">Ref {l.id}</span>
                    </div>
                    <Link href={`/listings/${l.id}`} className="text-lg font-medium hover:underline">{l.title}</Link>
                    <p className="text-sm text-muted">
                      {l.locality}, {l.city}, {formatINR(l.rent)}/month, {l.photos?.length ?? 0} photo{l.photos?.length === 1 ? "" : "s"}
                    </p>
                    {l.status === "blocked" && (
                      <p className="rounded-lg bg-claim-soft px-3 py-2 text-sm text-claim">Reason: {l.admin_note}. Contact TrustRent support to get it relisted.</p>
                    )}
                    <div className="mt-1 flex flex-wrap gap-2 text-sm">
                      {l.status !== "blocked" && <button type="button" onClick={() => act(() => setListingStatus(l.id, l.status === "paused" ? "live" : "paused"))}
                        className="rounded-md border border-line px-3 py-1 hover:border-ink/40">
                        {l.status === "paused" ? "Make live" : "Pause"}
                      </button>}
                      <button type="button" onClick={() => act(() => deleteOwnerListing(l.id))}
                        className="rounded-md px-3 py-1 text-claim hover:bg-claim-soft">
                        Delete
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
