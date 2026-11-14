"use client";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";
import { AuthFrame, FormError, PasswordField, SecondaryLink, SubmitButton } from "@/components/auth-ui";
import { AuthError, validatePassword } from "@/lib/auth";
import { useAuth } from "@/lib/auth-context";
function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const { resetPassword } = useAuth();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    const problem = validatePassword(password);
    if (problem) return setError(problem);
    if (password !== confirm) return setError("The passwords don't match.");
    setError(null);
    setBusy(true);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof AuthError ? err.message : "Could not change the password. Try again.");
    } finally {
      setBusy(false);
    }
  }
  if (!token) {
    return (
      <AuthFrame title="Reset link missing" subtitle="Open the link from the email we sent you, or ask for a new one.">
        <SecondaryLink href="/forgot-password">Send a new link</SecondaryLink>
      </AuthFrame>
    );
  }
  return (
    <AuthFrame title="Choose a new password" subtitle="Every other device will be signed out.">
      {done ? (
        <div className="flex flex-col gap-4">
          <p role="status" className="rounded-lg border border-vault/30 bg-vault-soft px-3 py-3 text-sm text-vault">Your password is changed.</p>
          <SecondaryLink href="/login">Sign in with the new password</SecondaryLink>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <PasswordField id="password" label="New password" autoComplete="new-password" value={password}
            onChange={(e) => setPassword(e.target.value)} hint="At least 8 characters, with a letter and a number." />
          <PasswordField id="confirm" label="Confirm new password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          <FormError message={error} />
          <SubmitButton busy={busy}>{busy ? "Saving..." : "Change password"}</SubmitButton>
          <p className="text-center text-sm text-muted">Link expired? <SecondaryLink href="/forgot-password">Send a new one</SecondaryLink></p>
        </form>
      )}
    </AuthFrame>
  );
}
export default function ResetPasswordPage() { // reset password
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}
