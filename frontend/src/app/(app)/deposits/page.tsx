"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { DepositCard } from "@/components/deposit-card";
import { apiMode } from "@/lib/api";
import { Deposit, myDeposits } from "@/lib/deposits";
function Deposits() {
  const highlight = useSearchParams().get("d");
  const [list, setList] = useState<Deposit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!apiMode) return;
    myDeposits().then(setList, (e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (highlight && list) document.getElementById(highlight)?.scrollIntoView({ block: "center" });
  }, [highlight, list]);
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl sm:text-4xl">Deposits</h1>
          <p className="text-muted">Every security deposit gets a tamper-proof receipt. At move-out it&apos;s settled against that receipt.</p>
        </div>
        <Link href="/deposits/lookup" className="rounded-lg border border-line px-4 py-2 text-sm hover:border-ink/40">Look up a deposit</Link>
      </div>
      {!apiMode ? (
        <p className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">Deposits need the TrustRent backend. Set NEXT_PUBLIC_API_URL and start the backend.</p>
      ) : error ? (
        <p role="alert" className="text-sm text-claim">{error}</p>
      ) : !list ? (
        <p className="text-sm text-muted" role="status">Loading...</p>
      ) : list.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">
          No deposits yet. After the owner confirms your visit, the home&apos;s page shows <strong>Pay deposit</strong>.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {list.map((d) => (
            <DepositCard key={d.id} d={d} highlight={d.id === highlight}
              onChange={(nd) => setList((l) => l!.map((x) => (x.id === nd.id ? nd : x)))} />
          ))}
        </div>
      )}
    </div>
  );
}
export default function DepositsPage() { // my deposits
  return (
    <Suspense>
      <Deposits />
    </Suspense>
  );
}
