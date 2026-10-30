"use client";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { AuthError, ProfileInput, validatePassword, validateProfile } from "@/lib/auth";
import { CountrySelect, FormError, PasswordField, PhoneField, SubmitButton, TextField } from "./auth-ui";
type Values = ProfileInput & { password: string; confirm: string };
export function ProfileForm({ // profile form
  initial,
  withPassword,
  submitLabel,
  busyLabel,
  onSubmit,
  lockEmail,
  requireConsent = false,
}: {
  initial?: Partial<ProfileInput>;
  withPassword: boolean;
  submitLabel: string;
  busyLabel: string;
  onSubmit: (values: ProfileInput & { password?: string }) => Promise<void>;
  lockEmail?: boolean;
  requireConsent?: boolean;
}) {
  const [v, setV] = useState<Values>({
    firstName: "", lastName: "", username: "", email: "", phone: "+91 ", country: "India",
    password: "", confirm: "",
    ...initial,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [consent, setConsent] = useState(false);
  const set = <K extends keyof Values>(k: K) => (value: Values[K]) => setV((s) => ({ ...s, [k]: value }));
  async function submit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const profile: ProfileInput = {
      firstName: v.firstName.trim(), lastName: v.lastName.trim(), username: v.username.trim().toLowerCase(),
      email: v.email.trim(), phone: v.phone.trim(), country: v.country,
    };
    const errs = validateProfile(profile);
    if (withPassword) {
      const pw = validatePassword(v.password);
      if (pw) errs.password = pw;
      if (v.password !== v.confirm) errs.confirm = "The passwords don't match.";
    }
    if (requireConsent && !consent) errs.consent = "Accept the Terms of Use and Privacy Policy to continue.";
    setErrors(errs);
    if (Object.keys(errs).length) {
      setFormError("Fix the highlighted fields to continue.");
      return;
    }
    setBusy(true);
    try {
      await onSubmit(withPassword ? { ...profile, password: v.password } : profile);
    } catch (err) {
      if (err instanceof AuthError && err.field) setErrors({ [err.field]: err.message });
      setFormError(err instanceof AuthError ? err.message : "Could not save your details. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField id="firstName" label="First name" autoComplete="given-name" value={v.firstName} onChange={(e) => set("firstName")(e.target.value)} error={errors.firstName} />
        <TextField id="lastName" label="Surname" autoComplete="family-name" value={v.lastName} onChange={(e) => set("lastName")(e.target.value)} error={errors.lastName} />
      </div>
      <TextField
        id="username"
        label="Username"
        autoComplete="username"
        value={v.username}
        onChange={(e) => set("username")(e.target.value.toLowerCase().replace(/\s/g, ""))}
        error={errors.username}
        hint="3 to 20 lowercase letters, numbers or underscores."
      />
      <TextField id="email" label="Email" type="email" autoComplete="email" value={v.email} readOnly={lockEmail} onChange={(e) => set("email")(e.target.value)} error={errors.email} />
      <PhoneField value={v.phone} onChange={set("phone")} error={errors.phone} />
      <CountrySelect value={v.country} onChange={set("country")} error={errors.country} />
      {withPassword && (
        <>
          <PasswordField id="password" label="Password" autoComplete="new-password" value={v.password} onChange={(e) => set("password")(e.target.value)} error={errors.password} hint="At least 8 characters, with a letter and a number." />
          <PasswordField id="confirm" label="Confirm password" autoComplete="new-password" value={v.confirm} onChange={(e) => set("confirm")(e.target.value)} error={errors.confirm} />
        </>
      )}
      {requireConsent && (
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1 h-4 w-4 accent-vault" />
          <span>
            I agree to the <Link href="/terms" target="_blank" className="text-vault underline">Terms of Use</Link> and{" "}
            <Link href="/privacy" target="_blank" className="text-vault underline">Privacy Policy</Link>, and consent to TrustRent
            processing my details to run my account.
            {errors.consent && <span className="mt-1 block text-xs text-claim">{errors.consent}</span>}
          </span>
        </label>
      )}
      <FormError message={formError} />
      <SubmitButton busy={busy}>{busy ? busyLabel : submitLabel}</SubmitButton>
    </form>
  );
}
