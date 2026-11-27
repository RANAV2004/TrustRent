"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { AuthFrame, FormError, PasswordField, SecondaryLink, SubmitButton, TextField } from "@/components/auth-ui";
import { AuthError, TwoFactorRequired } from "@/lib/auth";
import { afterSignIn, useAuth } from "@/lib/auth-context";

export default function LawyerLoginPage() { // lawyer sign in
  const { user, ready, signIn, signOut } = useAuth();
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const signingIn = useRef(false);
  useEffect(() => {
    if (ready && user && !signingIn.current) router.replace(afterSignIn(user, null));
  }, [ready, user, router]);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!identifier.trim() || !password) return setError("Enter the username and password we sent you.");
    setError(null);
    setBusy(true);
    signingIn.current = true;
    try {
      const u = await signIn(identifier, password);
      if (u.accountType !== "lawyer") { // a tenant or owner account: send them to the normal sign-in
        await signOut();
        signingIn.current = false;
        setError("This isn't a lawyer account. Use the main sign-in page instead.");
        return;
      }
      router.replace(afterSignIn(u, null));
    } catch (err) {
      signingIn.current = false;
      if (err instanceof TwoFactorRequired) { // an admin account: two-step sign-in lives on the main page
        setError("This isn't a lawyer account. Use the main sign-in page instead.");
        return;
      }
      setError(err instanceof AuthError ? err.message : "Could not sign you in. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthFrame title="Lawyer sign in" subtitle="Welcome back to TrustRent. Sign in with the details we sent you after verification.">
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <TextField id="identifier" label="Username or email" autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
        <div className="flex flex-col gap-1">
          <PasswordField id="password" label="Password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <Link href="/forgot-password" className="self-end text-sm text-vault underline-offset-2 hover:underline">
            Forgot password?
          </Link>
        </div>
        <FormError message={error} />
        <SubmitButton busy={busy}>{busy ? "Signing in..." : "Sign in as a lawyer"}</SubmitButton>
      </form>
      <div className="mt-8 flex flex-col gap-3 rounded-xl border border-line bg-surface p-4 text-sm">
        <p className="font-medium">Don&apos;t have sign-in details yet?</p>
        <p className="text-muted">Apply with your Bar Council enrolment details. We verify lawyers within 24 to 48 hours and email you a username and password.</p>
        <Link href="/lawyer-apply" className="w-fit rounded-lg border border-vault px-4 py-2 font-medium text-vault hover:bg-vault-soft">
          Apply to get verified
        </Link>
      </div>
      <p className="mt-8 text-center text-sm text-muted">
        Not a lawyer? <SecondaryLink href="/login">Sign in here</SecondaryLink>
      </p>
    </AuthFrame>
  );
}
