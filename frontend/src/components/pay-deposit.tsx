"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { DemoCheckout, payWithRazorpay } from "@/components/checkout";
import { useAuth } from "@/lib/auth-context";
import { createOrder, Order, PaymentResult } from "@/lib/deposits";
import { formatINR } from "@/lib/format";
import type { Listing } from "@/lib/listings";
export function PayDepositCard({ l }: { l: Listing }) { // pay deposit card
  const { user, refreshUser } = useAuth();
  const router = useRouter();
  const [order, setOrder] = useState<Order | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!user) return null;
  const done = (r: PaymentResult) => {
    refreshUser();
    router.push(`/deposits?d=${r.depositId}`);
  };
  async function start() {
    setError(null);
    setBusy(true);
    try {
      const o = await createOrder({ purpose: "deposit", listingId: l.id });
      if (o.provider === "razorpay") done(await payWithRazorpay(o));
      else setOrder(o);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't start the payment.");
    } finally {
      setBusy(false);
    }
  }
  if (order) return <DemoCheckout order={order} onPaid={done} onCancel={() => setOrder(null)} />;
  return (
    <section className="flex flex-col gap-2 rounded-2xl border border-vault/30 bg-vault-soft p-5">
      <h2 className="text-base">Ready to rent this home?</h2>
      <p className="text-sm">Pay the {formatINR(l.deposit)} security deposit to TrustRent. You get a receipt recorded on the blockchain, and at move-out the refund is settled against that receipt.</p>
      {!user.idVerified ? (
        <Link href={`/premium?from=${l.id}`} className="mt-1 w-fit text-sm font-medium text-vault hover:underline">Verify your ID first</Link>
      ) : (
        <button type="button" onClick={start} disabled={busy}
          className="mt-1 rounded-lg bg-vault px-4 py-2.5 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">
          {busy ? "Starting..." : `Pay deposit ${formatINR(l.deposit)}`}
        </button>
      )}
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
    </section>
  );
}
