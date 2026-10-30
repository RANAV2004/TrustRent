"use client";
import { FormEvent, useState } from "react";
import { AuthFrame, FormError, SecondaryLink, SubmitButton, TextField } from "@/components/auth-ui";
import { AuthError } from "@/lib/auth";
import { useAuth } from "@/lib/auth-context";
export default function ForgotPasswordPage() { // forgot password
  const { requestPasswordReset } = useAuth();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await requestPasswordReset(email.trim());
      setSent(true);
    } catch (err) {
      setError(err instanceof AuthError ? err.message : "Could not send the link. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthFrame title="Reset your password" subtitle="Enter the email on your account and we'll send you a link to set a new password.">
      {sent ? (
        <div className="flex flex-col gap-4">
          <p role="status" className="rounded-lg border border-vault/30 bg-vault-soft px-3 py-3 text-sm text-vault">
            If an account uses {email}, a reset link is on its way. It expires in 30 minutes.
          </p>
          <button type="button" onClick={() => setSent(false)} className="text-sm text-vault hover:underline">
            Use a different email
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <TextField id="email" label="Email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <FormError message={error} />
          <SubmitButton busy={busy}>{busy ? "Sending..." : "Send reset link"}</SubmitButton>
        </form>
      )}
      <p className="mt-8 text-center text-sm text-muted">
        Remembered it? <SecondaryLink href="/login">Back to sign in</SecondaryLink>
      </p>
    </AuthFrame>
  );
}
