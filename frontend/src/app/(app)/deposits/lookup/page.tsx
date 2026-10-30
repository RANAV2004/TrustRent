"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { DepositCard } from "@/components/deposit-card";
import { apiMode } from "@/lib/api";
import { Deposit, lookupDeposit } from "@/lib/deposits";
function Lookup() {
  const router = useRouter();
  const q = useSearchParams().get("q") ?? "";
  const [text, setText] = useState(q);
  const [result, setResult] = useState<Deposit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!q || !apiMode) return;
    let alive = true;
    Promise.resolve().then(() => { if (alive) { setLoading(true); setError(null); } });
    lookupDeposit(q).then(
      (d) => { if (alive) { setResult(d); setLoading(false); } },
      (e) => { if (alive) { setResult(null); setError(e.message); setLoading(false); } },
    );
    return () => { alive = false; };
  }, [q]);
  function submit(e: FormEvent) {
    e.preventDefault();
    if (text.trim()) router.push(`/deposits/lookup?q=${encodeURIComponent(text.trim())}`);
  }
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl sm:text-4xl">Look up a deposit</h1>
        <p className="max-w-2xl text-muted">Enter a deposit ID (DEP-...) or a receipt hash (0x...). TrustRent recomputes the deposit&apos;s fingerprint from today&apos;s records and checks it against the receipt, so any later change is caught.</p>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row" role="search">
        <label htmlFor="dq" className="sr-only">Deposit ID or receipt hash</label>
        <input id="dq" value={text} onChange={(e) => setText(e.target.value)} placeholder="DEP-1A2B3C4D or 0x..."
          className="min-w-0 flex-1 rounded-xl border border-line bg-surface px-4 py-3 text-[15px] focus:border-vault focus:outline-none" />
        <button type="submit" className="rounded-xl bg-vault px-6 py-3 text-sm font-medium text-white hover:bg-vault-deep">Look up</button>
      </form>
      {!apiMode ? (
        <p className="text-sm text-muted">Lookup needs the TrustRent backend.</p>
      ) : loading ? (
        <p className="text-sm text-muted" role="status">Checking...</p>
      ) : error ? (
        <p role="alert" className="text-sm text-claim">{error}</p>
      ) : result ? (
        <DepositCard d={result} onChange={setResult} />
      ) : null}
    </div>
  );
}
export default function LookupPage() { // receipt lookup
  return (
    <Suspense>
      <Lookup />
    </Suspense>
  );
}
