"use client";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { AuthFrame, FormError, PasswordField, SecondaryLink, SubmitButton, TextField } from "@/components/auth-ui";
import { AuthError, authMode, DEMO_OTP, TwoFactorRequired, validatePassword } from "@/lib/auth";
import { afterSignIn, useAuth } from "@/lib/auth-context";
export default function ForgotPasswordPage() {
  const { requestPasswordReset, resetPassword } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  async function sendCode(e?: FormEvent) {
    e?.preventDefault();
    setError(null);
    setFieldErrors({});
    setBusy(true);
    try {
      await requestPasswordReset(email.trim());
      setSent(true);
    } catch (err) {
      setError(err instanceof AuthError ? err.message : "Could not send the code. Try again.");
    } finally {
      setBusy(false);
    }
  }
  async function reset(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const pwError = validatePassword(password);
    if (!/^\d{6}$/.test(code.trim()) || pwError) {
      setFieldErrors({
        ...(!/^\d{6}$/.test(code.trim()) ? { code: "Enter the 6-digit code from the email." } : {}),
        ...(pwError ? { password: pwError } : {}),
      });
      return;
    }
    setFieldErrors({});
    setBusy(true);
    try {
      const u = await resetPassword(email.trim(), code.trim(), password);
      router.replace(afterSignIn(u, null));
    } catch (err) {
      if (err instanceof TwoFactorRequired) {
        router.replace("/login?reset=1");
        return;
      }
      if (err instanceof AuthError && err.field) setFieldErrors({ [err.field]: err.message });
      else setError(err instanceof AuthError ? err.message : "Could not reset the password. Try again.");
      setBusy(false);
    }
  }
  return (
    <AuthFrame title="Reset your password" subtitle="Enter the email on your account and we'll send you a code to set a new password.">
      {sent ? (
        <form onSubmit={reset} className="flex flex-col gap-4" noValidate>
          <p role="status" className="rounded-lg border border-vault/30 bg-vault-soft px-3 py-3 text-sm text-vault">
            If an account uses {email}, a 6-digit code is on its way. It expires in 10 minutes.
            {authMode === "demo" && <> Demo code: <strong>{DEMO_OTP}</strong></>}
          </p>
          <TextField id="code" label="Code from the email" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
            value={code} onChange={(e) => setCode(e.target.value)} error={fieldErrors.code} />
          <PasswordField id="password" label="New password" autoComplete="new-password" value={password}
            onChange={(e) => setPassword(e.target.value)} error={fieldErrors.password}
            hint="At least 8 characters, with a letter and a number." />
          <FormError message={error} />
          <SubmitButton busy={busy}>{busy ? "Saving..." : "Set new password"}</SubmitButton>
          <div className="flex justify-between text-sm">
            <button type="button" onClick={() => sendCode()} disabled={busy} className="text-vault hover:underline">
              Send a new code
            </button>
            <button type="button" onClick={() => { setSent(false); setCode(""); setPassword(""); setError(null); }}
              className="text-vault hover:underline">
              Use a different email
            </button>
          </div>
        </form>
      ) : (
        <form onSubmit={sendCode} className="flex flex-col gap-4" noValidate>
          <TextField id="email" label="Email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <FormError message={error} />
          <SubmitButton busy={busy}>{busy ? "Sending..." : "Send reset code"}</SubmitButton>
        </form>
      )}
      <p className="mt-8 text-center text-sm text-muted">
        Remembered it? <SecondaryLink href="/login">Back to sign in</SecondaryLink>
      </p>
    </AuthFrame>
  );
}
