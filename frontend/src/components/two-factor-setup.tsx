"use client";
import { FormEvent, useState } from "react";
import { ApiError, setToken } from "@/lib/api";
import { confirmTwoFactor, startTwoFactor, TwoFactorSetup as Setup } from "@/lib/admin";
import { useAuth } from "@/lib/auth-context";

export function RecoveryCodes({ codes, onDone, doneLabel = "I've saved them" }: { codes: string[]; onDone: () => void; doneLabel?: string }) {
  const [copied, setCopied] = useState(false);
  const text = `TrustRent admin recovery codes (each works once)\n${codes.join("\n")}`;
  function download() {
    const url = URL.createObjectURL(new Blob([text + "\n"], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "trustrent-recovery-codes.txt";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm">If you lose your phone, each of these codes lets you sign in once. <strong>Save them somewhere safe now</strong> (a password manager or a printed copy). They won&apos;t be shown again.</p>
      <ul className="grid grid-cols-2 gap-2 rounded-xl border border-line bg-mist p-4 font-mono text-sm">
        {codes.map((c) => <li key={c}>{c}</li>)}
      </ul>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={download} className="rounded-lg border border-line px-3 py-1.5 text-sm hover:border-ink/40">Download</button>
        <button type="button" onClick={() => navigator.clipboard?.writeText(text).then(() => setCopied(true))}
          className="rounded-lg border border-line px-3 py-1.5 text-sm hover:border-ink/40">{copied ? "Copied" : "Copy"}</button>
        <button type="button" onClick={onDone} className="rounded-lg bg-vault px-4 py-1.5 text-sm font-medium text-white hover:bg-vault-deep">{doneLabel}</button>
      </div>
    </div>
  );
}

export function TwoFactorSetup({ required, onFinished }: { required: boolean; onFinished: () => void }) {
  const { refreshUser } = useAuth();
  const [setup, setSetup] = useState<Setup | null>(null);
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function begin() {
    setError(null);
    setBusy(true);
    try {
      setSetup(await startTwoFactor());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start. Try again.");
    } finally {
      setBusy(false);
    }
  }
  async function confirm(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const r = await confirmTwoFactor(code.trim());
      setToken(r.access_token); // this session has now passed the authenticator check
      setCodes(r.recoveryCodes);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't check the code. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="mx-auto flex max-w-xl flex-col gap-5 rounded-2xl border border-line bg-surface p-6">
      <div>
        <h1 className="text-2xl">Set up two-step sign-in</h1>
        <p className="mt-1 text-sm text-muted">
          {required ? "The admin console can see every user's documents, so it needs more than a password. " : ""}
          After your password, you&apos;ll enter a 6-digit code from an authenticator app on your phone, such as Google Authenticator or Microsoft Authenticator.
        </p>
      </div>
      {codes ? (
        <RecoveryCodes codes={codes} onDone={() => { refreshUser().then(onFinished); }} doneLabel="I've saved them: open the console" />
      ) : !setup ? (
        <button type="button" disabled={busy} onClick={begin}
          className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">
          {busy ? "Starting..." : "Start setup"}
        </button>
      ) : (
        <form onSubmit={confirm} className="flex flex-col gap-4">
          <ol className="flex list-decimal flex-col gap-2 pl-5 text-sm">
            <li>Install an authenticator app on your phone.</li>
            <li>In the app, add an account and scan this QR code.</li>
          </ol>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`data:image/svg+xml;utf8,${encodeURIComponent(setup.qrSvg)}`} alt="QR code for your authenticator app"
            width={200} height={200} className="rounded-lg border border-line bg-white p-2" />
          <p className="text-xs text-muted">Can&apos;t scan? Enter this key in the app instead: <span className="font-mono break-all text-ink">{setup.secret}</span></p>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">3. Enter the 6-digit code the app shows</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" maxLength={6}
              className="w-40 rounded-lg border border-line px-3 py-2 font-mono text-lg tracking-widest" />
          </label>
          {error && <p role="alert" className="text-sm text-claim">{error}</p>}
          <button type="submit" disabled={busy || code.trim().length !== 6}
            className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">
            {busy ? "Checking..." : "Turn on two-step sign-in"}
          </button>
        </form>
      )}
      {error && !setup && <p role="alert" className="text-sm text-claim">{error}</p>}
    </section>
  );
}
