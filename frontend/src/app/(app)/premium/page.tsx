"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";
import { PremiumBadge } from "@/components/listing-ui";
import { DemoCheckout, payWithRazorpay } from "@/components/checkout";
import { apiMode } from "@/lib/api";
import { createOrder, Order } from "@/lib/deposits";
import { AuthError, isPremium } from "@/lib/auth";
import { useAuth } from "@/lib/auth-context";
import { formatINR } from "@/lib/format";
import { allListings, EARLY_ACCESS_HOURS, earlyAccessHoursLeft } from "@/lib/listings";
import { ID_DOCS } from "@/lib/owner";
const PLANS = [
  { id: "week", name: "1 week", days: 7, price: 99, note: "For a quick move" },
  { id: "month", name: "1 month", days: 30, price: 299, note: "Most people pick this", best: true },
  { id: "quarter", name: "3 months", days: 90, price: 699, note: "If you're not in a hurry" },
];
function Premium() {
  const { user, verifyIdentity, activatePremium, refreshUser } = useAuth();
  const [order, setOrder] = useState<Order | null>(null);
  const from = useSearchParams().get("from");
  const [planId, setPlanId] = useState("month");
  const [step, setStep] = useState<"plans" | "id" | "pending" | "pay" | "done">("plans");
  const [docType, setDocType] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (!user) return null;
  const active = isPremium(user);
  const plan = PLANS.find((p) => p.id === planId)!;
  const newNow = allListings().filter((l) => earlyAccessHoursLeft(l) > 0).length;
  async function run(fn: () => Promise<unknown>, next: typeof step) {
    setError(null);
    setBusy(true);
    try {
      await fn();
      setStep(next);
    } catch (e) {
      setError(e instanceof AuthError ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }
  function submitId(e: FormEvent) {
    e.preventDefault();
    if (!docType) return setError("Choose the document you're uploading.");
    if (!file) return setError("Upload a photo or scan of the document.");
    if (!consent) return setError("Tick the consent box to continue.");
    setError(null);
    setBusy(true);
    verifyIdentity(docType, file)
      .then((u) => setStep(u.idVerified ? "pay" : "pending"))
      .catch((e) => setError(e instanceof Error ? e.message : "Something went wrong. Try again."))
      .finally(() => setBusy(false));
  }
  async function pay() {
    if (!apiMode) return run(() => activatePremium(plan.id, plan.days), "done");
    setError(null);
    setBusy(true);
    try {
      const o = await createOrder({ purpose: "premium", planId: plan.id });
      if (o.provider === "razorpay") {
        await payWithRazorpay(o);
        await refreshUser();
        setStep("done");
      } else {
        setOrder(o);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Payment failed. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl sm:text-4xl">TrustRent Premium</h1>
          {active && <PremiumBadge />}
        </div>
        <p className="max-w-2xl text-muted">
          Good homes go fast. Premium members can contact owners of new listings in their first {EARLY_ACCESS_HOURS} hours, before anyone else,
          and carry a Verified Premium badge that tells owners TrustRent has checked their identity.
        </p>
        {active && (
          <p className="w-fit rounded-lg bg-vault-soft px-3 py-2 text-sm text-vault">
            You&apos;re Premium until {new Date(user.premium!.until).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}. Buying another plan adds to it.
          </p>
        )}
      </section>
      <section className="grid gap-4 md:grid-cols-3" aria-label="What you get">
        {[
          { t: "Early access", d: `Message and book visits for new homes in their first ${EARLY_ACCESS_HOURS} hours. ${newNow} home${newNow === 1 ? " is" : "s are"} in early access right now.` },
          { t: "Verified Premium badge", d: "Shown on your profile and messages, so owners know your identity was checked." },
          { t: "Same TrustRent protection", d: "Your deposit is still held in a vault. Premium never changes the rules of a lease." },
        ].map((b) => (
          <div key={b.t} className="rounded-2xl border border-line bg-surface p-5">
            <h2 className="text-base">{b.t}</h2>
            <p className="mt-1 text-sm text-muted">{b.d}</p>
          </div>
        ))}
      </section>
      {step === "done" ? (
        <section className="flex flex-col items-start gap-3 rounded-2xl border border-vault/30 bg-vault-soft p-6">
          <PremiumBadge />
          <h2 className="text-2xl">You&apos;re Premium</h2>
          <p className="text-sm">Early access is on. New homes now show &ldquo;you have early access&rdquo; and you can message their owners straight away.</p>
          <Link href={from ? `/listings/${from}` : "/search"} className="rounded-lg bg-vault px-4 py-2.5 text-sm font-medium text-white hover:bg-vault-deep">
            {from ? "Back to the home you were viewing" : "Search homes"}
          </Link>
        </section>
      ) : step === "plans" ? (
        <section className="flex flex-col gap-4">
          <h2 className="text-xl">Choose a plan</h2>
          <div role="radiogroup" aria-label="Plans" className="grid gap-3 md:grid-cols-3">
            {PLANS.map((p) => (
              <label key={p.id} className={`relative flex cursor-pointer flex-col gap-1 rounded-2xl border p-5 ${planId === p.id ? "border-vault bg-vault-soft" : "border-line bg-surface hover:border-ink/30"}`}>
                <input type="radio" name="plan" value={p.id} checked={planId === p.id} onChange={() => setPlanId(p.id)} className="sr-only" />
                {p.best && <span className="absolute top-3 right-3 rounded-full bg-vault px-2 py-0.5 text-[11px] font-medium text-white">Popular</span>}
                <span className="font-semibold">{p.name}</span>
                <span className="font-display text-3xl font-semibold tabular">{formatINR(p.price)}</span>
                <span className="text-sm text-muted">{formatINR(Math.round(p.price / p.days))} a day, {p.note}</span>
              </label>
            ))}
          </div>
          <button type="button" onClick={() => setStep(user.idVerified ? "pay" : "id")} className="w-fit rounded-lg bg-vault px-6 py-3 text-sm font-medium text-white hover:bg-vault-deep">
            Continue with {plan.name}
          </button>
        </section>
      ) : step === "id" ? (
        <form onSubmit={submitId} className="flex max-w-xl flex-col gap-4 rounded-2xl border border-line bg-surface p-6" noValidate>
          <div>
            <p className="text-sm text-muted">Step 1 of 2</p>
            <h2 className="text-xl">Verify your identity</h2>
            <p className="mt-1 text-sm text-muted">The badge means TrustRent has checked who you are, so we need one ID document. For Aadhaar, upload the masked version (first 8 digits hidden), which you can download from the UIDAI website.</p>
          </div>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">Document</span>
            <select value={docType} onChange={(e) => setDocType(e.target.value)} className="rounded-lg border border-line px-3 py-2.5">
              <option value="">Choose a document</option>
              {ID_DOCS.map((d) => <option key={d}>{d}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">Photo or scan</span>
            <input type="file" accept="image/*,application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="rounded-lg border border-line px-3 py-2 file:mr-3 file:rounded-md file:border-0 file:bg-vault-soft file:px-2 file:py-1 file:text-vault" />
            <span className="text-xs text-muted">{apiMode ? "Stored encrypted (AES-256) and used only to verify you." : "Demo: the file is not uploaded or stored anywhere."}</span>
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1 h-4 w-4 accent-vault" />
            I agree that TrustRent may use this document only to verify my identity, and will delete it after review.
          </label>
          {error && <p role="alert" className="text-sm text-claim">{error}</p>}
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className="rounded-lg bg-vault px-5 py-2.5 text-sm font-medium text-white hover:bg-vault-deep">{busy ? "Checking..." : "Verify identity"}</button>
            <button type="button" onClick={() => setStep("plans")} className="px-3 text-sm text-muted hover:text-ink">Back</button>
          </div>
        </form>
      ) : step === "pending" ? (
        <section className="flex max-w-xl flex-col gap-3 rounded-2xl border border-line bg-surface p-6">
          <h2 className="text-xl">We&apos;re checking your ID</h2>
          <p className="text-sm text-muted">A TrustRent admin reviews every ID, usually within a day. Once it&apos;s approved you can buy Premium and pay deposits.</p>
          <button type="button" disabled={busy}
            onClick={() => { setBusy(true); refreshUser().then((u) => { if (u?.idVerified) setStep("pay"); else setError("Not approved yet. Try again later."); }).finally(() => setBusy(false)); }}
            className="w-fit rounded-lg border border-line px-4 py-2 text-sm hover:border-ink/40">Check again</button>
          {error && <p role="alert" className="text-sm text-muted">{error}</p>}
        </section>
      ) : order ? (
        <div className="max-w-xl">
          <DemoCheckout order={order} onCancel={() => setOrder(null)}
            onPaid={() => { refreshUser().then(() => { setOrder(null); setStep("done"); }); }} />
        </div>
      ) : (
        <section className="flex max-w-xl flex-col gap-4 rounded-2xl border border-line bg-surface p-6">
          <div>
            <p className="text-sm text-muted">{user.idVerified ? "Last step" : "Step 2 of 2"}</p>
            <h2 className="text-xl">Pay for {plan.name} of Premium</h2>
          </div>
          <dl className="flex justify-between border-y border-line py-3 text-sm">
            <dt>{plan.name} Premium</dt>
            <dd className="font-semibold tabular">{formatINR(plan.price)}</dd>
          </dl>
          <p className="text-xs text-muted">{apiMode ? "Secure payment by Razorpay: UPI, cards or net banking." : "Demo checkout: no money is taken."}</p>
          {error && <p role="alert" className="text-sm text-claim">{error}</p>}
          <div className="flex gap-2">
            <button type="button" disabled={busy} onClick={pay}
              className="rounded-lg bg-vault px-5 py-2.5 text-sm font-medium text-white hover:bg-vault-deep">
              {busy ? "Processing..." : `Pay ${formatINR(plan.price)}`}
            </button>
            <button type="button" onClick={() => setStep("plans")} className="px-3 text-sm text-muted hover:text-ink">Change plan</button>
          </div>
        </section>
      )}
    </div>
  );
}
export default function PremiumPage() { // premium
  return (
    <Suspense>
      <Premium />
    </Suspense>
  );
}
