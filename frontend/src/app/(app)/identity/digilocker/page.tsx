"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { digilockerComplete } from "@/lib/trust";

function Callback() {
  const params = useSearchParams();
  const { refreshUser } = useAuth();
  const code = params.get("code");
  const state = params.get("state");
  const missing = !code || !state ? { ok: false, text: params.get("error_description") || "DigiLocker didn't send a sign-in code. Try again." } : null;
  const [result, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const msg = missing ?? result;
  const once = useRef(false);
  useEffect(() => {
    if (once.current || !code || !state) return;
    once.current = true;
    digilockerComplete(code, state).then(
      async (r) => { await refreshUser(); setMsg({ ok: r.matched, text: r.message }); },
      (e) => setMsg({ ok: false, text: e.message }),
    );
  }, [code, state, refreshUser]);
  return (
    <div className="mx-auto flex max-w-lg flex-col gap-4 rounded-2xl border border-line bg-surface p-6">
      <h1 className="text-2xl">DigiLocker verification</h1>
      {!msg ? <p className="text-sm text-muted" role="status">Checking with DigiLocker...</p> : (
        <p role={msg.ok ? "status" : "alert"} className={`rounded-lg px-3 py-2 text-sm ${msg.ok ? "bg-vault-soft text-vault" : "bg-amber-soft"}`}>{msg.text}</p>
      )}
      <Link href="/premium" className="text-sm text-vault hover:underline">Back to Premium and verification</Link>
    </div>
  );
}
export default function DigilockerCallbackPage() { // digilocker return
  return <Suspense><Callback /></Suspense>;
}
