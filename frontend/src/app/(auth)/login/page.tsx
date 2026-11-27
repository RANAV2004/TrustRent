"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import {
  AuthFrame, Divider, FormError, PasswordField, SecondaryLink, SubmitButton, TextField,
} from "@/components/auth-ui";
import { AuthError, authMode, TwoFactorRequired, User } from "@/lib/auth";
import { GOOGLE_CLIENT_ID, GoogleButton } from "@/components/google-button";
import { afterSignIn, useAuth } from "@/lib/auth-context";
function CodeStep({ challenge, onDone, onCancel }: { challenge: string; onDone: (u: User) => void; onCancel: () => void }) {
  const { verifyTwoFactor } = useAuth();
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      onDone(await verifyTwoFactor(challenge, code));
    } catch (err) {
      setError(err instanceof AuthError ? err.message : "Could not check the code. Try again.");
      setBusy(false);
    }
  }
  return (
    <AuthFrame title="Two-step sign-in" subtitle={recovery ? "Enter one of the recovery codes you saved when you set up two-step sign-in." : "Open your authenticator app and enter the 6-digit code for TrustRent."}>
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <TextField id="code" label={recovery ? "Recovery code" : "6-digit code"} autoFocus autoComplete="one-time-code"
          inputMode={recovery ? "text" : "numeric"} maxLength={recovery ? 12 : 6} placeholder={recovery ? "abcd-efgh" : "123456"}
          value={code} onChange={(e) => setCode(e.target.value)} />
        <FormError message={error} />
        <SubmitButton busy={busy}>{busy ? "Checking..." : "Verify and sign in"}</SubmitButton>
      </form>
      <div className="mt-6 flex justify-between text-sm">
        <button type="button" onClick={() => { setRecovery((r) => !r); setCode(""); setError(null); }} className="text-vault hover:underline">
          {recovery ? "Use my authenticator app" : "Lost your phone? Use a recovery code"}
        </button>
        <button type="button" onClick={onCancel} className="text-muted hover:text-ink">Cancel</button>
      </div>
    </AuthFrame>
  );
}
function LoginForm() {
  const { user, ready, signIn, signInWithGoogle } = useAuth();
  const [challenge, setChallenge] = useState<string | null>(null);
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [googleOpen, setGoogleOpen] = useState(false);
  const [googleEmail, setGoogleEmail] = useState("");
  const signingIn = useRef(false);
  useEffect(() => {
    if (ready && user && !signingIn.current) router.replace(afterSignIn(user, next));
  }, [ready, user, next, router]);
  async function run(action: () => Promise<User>) {
    setError(null);
    setBusy(true);
    signingIn.current = true;
    try {
      const u = await action();
      router.replace(afterSignIn(u, next));
    } catch (err) {
      if (err instanceof TwoFactorRequired) return setChallenge(err.challenge);
      signingIn.current = false;
      setError(err instanceof AuthError ? err.message : "Could not sign you in. Try again.");
    } finally {
      setBusy(false);
    }
  }
  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!identifier.trim() || !password) {
      setError("Enter your username or email and your password.");
      return;
    }
    run(() => signIn(identifier, password));
  }
  if (challenge) {
    return <CodeStep challenge={challenge} onDone={(u) => router.replace(afterSignIn(u, next))}
      onCancel={() => { signingIn.current = false; setChallenge(null); setPassword(""); }} />;
  }
  return (
    <AuthFrame title="Sign in" subtitle="Welcome back to TrustRent.">
      {params.get("reset") === "1" && (
        <p role="status" className="mb-4 rounded-lg border border-vault/30 bg-vault-soft px-3 py-2 text-sm text-vault">
          Password changed. Sign in with your new password.
        </p>
      )}
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <TextField id="identifier" label="Username or email" autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
        <div className="flex flex-col gap-1">
          <PasswordField id="password" label="Password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <Link href="/forgot-password" className="self-end text-sm text-vault underline-offset-2 hover:underline">
            Forgot password?
          </Link>
        </div>
        <FormError message={error} />
        <SubmitButton busy={busy}>{busy ? "Signing in..." : "Sign in"}</SubmitButton>
      </form>
      <Divider />
      <div className="flex flex-col gap-3">
        {GOOGLE_CLIENT_ID && authMode === "api" ? (
          <GoogleButton onCredential={(credential) => run(() => signInWithGoogle(credential))} />
        ) : !googleOpen ? (
          <button
            type="button"
            onClick={() => setGoogleOpen(true)}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-line bg-surface px-4 py-3 text-[15px] font-medium hover:border-ink/40"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z" />
            </svg>
            Continue with Google
          </button>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              run(() => signInWithGoogle(googleEmail));
            }}
            className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4"
          >
            <p className="text-sm text-muted">Demo: real Google sign-in needs a Google client ID (see README). Enter the Google email you&apos;d sign in with.</p>
            <TextField id="google-email" label="Google email" type="email" value={googleEmail} onChange={(e) => setGoogleEmail(e.target.value)} />
            <div className="flex gap-2">
              <button type="submit" disabled={busy} className="flex-1 rounded-lg bg-vault px-4 py-2.5 text-sm font-medium text-white hover:bg-vault-deep">Continue</button>
              <button type="button" onClick={() => setGoogleOpen(false)} className="rounded-lg px-4 py-2.5 text-sm text-muted hover:text-ink">Cancel</button>
            </div>
          </form>
        )}
      </div>
      <p className="mt-8 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-center text-sm text-muted">
        <span>New to TrustRent? <SecondaryLink href="/signup">Create an account</SecondaryLink></span>
        <span aria-hidden="true">·</span>
        <SecondaryLink href="/lawyer-login">Lawyer</SecondaryLink>
      </p>
    </AuthFrame>
  );
}
export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
