"use client";
import Link from "next/link";
import { InputHTMLAttributes, ReactNode, useState } from "react";
import { AccountType, authMode, COUNTRIES } from "@/lib/auth";
import { Logo } from "./app-shell";
export function AuthFrame({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children: ReactNode }) { // auth frame
  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-vault-deep p-10 text-white lg:flex">
        <div aria-hidden="true" className="absolute inset-0 bg-cover bg-center opacity-40" style={{ backgroundImage: "url(/auth-bg.jpg)" }} />
        <div aria-hidden="true" className="absolute inset-0 bg-linear-to-t from-vault-deep via-vault-deep/80 to-vault-deep/55" />
        <div className="relative [--logo-rent:#5cc4a6] [--vault:#2f9e82] [&_a]:text-white">
          <Logo />
        </div>
        <div className="relative flex max-w-md flex-col gap-6">
          <h2 className="text-4xl leading-tight text-white">Rent a home without worrying about your deposit.</h2>
          <ul className="flex flex-col gap-4 text-[15px] text-white/85">
            <li className="flex gap-3"><Check />Every landlord is identity-verified before you see their home.</li>
            <li className="flex gap-3"><Check />Your deposit sits in a vault, not in the landlord&apos;s account.</li>
            <li className="flex gap-3"><Check />Message owners and book a time to see the home, all in one place.</li>
          </ul>
        </div>
        <p className="relative text-xs text-white/60">TrustRent, final year project, SVIIT Indore</p>
      </aside>
      <main className="flex flex-col items-center justify-center px-4 py-10 sm:px-8">
        <div className="mb-8 lg:hidden">
          <Logo />
        </div>
        <div className="w-full max-w-md">
          <h1 className="text-3xl">{title}</h1>
          {subtitle && <p className="mt-2 text-muted">{subtitle}</p>}
          <div className="mt-8">{children}</div>
          {authMode === "demo" && (
            <p className="mt-8 rounded-lg border border-line bg-surface px-3 py-2 text-xs text-muted">
              Demo mode: accounts are saved in this browser until the backend is connected.
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
function Check() {
  return (
    <svg className="mt-1 shrink-0" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="8" fill="rgba(255,255,255,.18)" />
      <path d="M4.5 8.3 7 10.6l4.6-5" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
const inputBase =
  "w-full rounded-lg border bg-surface px-3 py-2.5 text-[15px] text-ink placeholder:text-muted/70 focus:outline-none focus:ring-2 focus:ring-vault/20";
export function TextField({ // text field
  label,
  error,
  hint,
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: string; id: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">{label}</label>
      <input
        id={id}
        {...props}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        className={`${inputBase} ${error ? "border-claim focus:border-claim" : "border-line focus:border-vault"}`}
      />
      {error ? (
        <span id={`${id}-error`} className="text-xs text-claim">{error}</span>
      ) : hint ? (
        <span id={`${id}-hint`} className="text-xs text-muted">{hint}</span>
      ) : null}
    </div>
  );
}
export function PasswordField(props: Omit<Parameters<typeof TextField>[0], "type">) { // password field
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <TextField {...props} type={show ? "text" : "password"} />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        className="absolute top-7.5 right-2 rounded-md px-2 py-1.5 text-xs font-medium text-vault hover:bg-vault-soft"
        aria-label={show ? "Hide password" : "Show password"}
      >
        {show ? "Hide" : "Show"}
      </button>
    </div>
  );
}
export function CountrySelect({ value, onChange, error }: { value: string; onChange: (v: string) => void; error?: string }) { // country select
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor="country" className="text-sm font-medium">Country</label>
      <select
        id="country"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={error ? true : undefined}
        className={`${inputBase} ${error ? "border-claim" : "border-line focus:border-vault"}`}
      >
        <option value="">Choose your country</option>
        {COUNTRIES.map((c) => (
          <option key={c.name} value={c.name}>{c.name}</option>
        ))}
      </select>
      {error && <span className="text-xs text-claim">{error}</span>}
    </div>
  );
}
export function PhoneField({ // phone field
  value,
  onChange,
  error,
  id = "phone",
  label = "Phone number",
}: {
  value: string;
  onChange: (v: string) => void;
  error?: string;
  id?: string;
  label?: string;
}) {
  const dials = Array.from(new Set(COUNTRIES.map((c) => c.dial)));
  const [code, ...rest] = value.split(" ");
  const dial = dials.includes(code) ? code : "+91";
  const number = dials.includes(code) ? rest.join(" ") : value;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">{label}</label>
      <div className="flex gap-2">
        <select
          aria-label="Country code"
          value={dial}
          onChange={(e) => onChange(`${e.target.value} ${number}`)}
          className={`${inputBase.replace("w-full ", "")} w-24 shrink-0 border-line focus:border-vault`}
        >
          {dials.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <input
          id={id}
          type="tel"
          inputMode="numeric"
          autoComplete="tel-national"
          value={number}
          onChange={(e) => onChange(`${dial} ${e.target.value.replace(/[^\d ]/g, "")}`)}
          placeholder="98765 43210"
          aria-invalid={error ? true : undefined}
          className={`${inputBase.replace("w-full ", "")} min-w-0 flex-1 ${error ? "border-claim" : "border-line focus:border-vault"}`}
        />
      </div>
      {error && <span className="text-xs text-claim">{error}</span>}
    </div>
  );
}
export function Divider({ label = "or" }: { label?: string }) { // divider
  return (
    <div className="my-6 flex items-center gap-3 text-xs text-muted">
      <span className="h-px flex-1 bg-line" />
      {label}
      <span className="h-px flex-1 bg-line" />
    </div>
  );
}
export function SubmitButton({ busy, children }: { busy?: boolean; children: ReactNode }) { // submit button
  return (
    <button
      type="submit"
      disabled={busy}
      className="w-full rounded-lg bg-vault px-4 py-3 text-[15px] font-medium text-white hover:bg-vault-deep disabled:cursor-wait disabled:bg-vault/60"
    >
      {children}
    </button>
  );
}
export function SecondaryLink({ href, children }: { href: string; children: ReactNode }) { // secondary link
  return (
    <Link href={href} className="font-medium text-vault underline-offset-2 hover:underline">
      {children}
    </Link>
  );
}
export function FormError({ message }: { message: string | null }) { // form error
  if (!message) return null;
  return (
    <p role="alert" className="rounded-lg border border-claim/30 bg-claim-soft px-3 py-2.5 text-sm text-claim">
      {message}
    </p>
  );
}
export function AccountTypeToggle({ value, onChange, legend = "I am...", hint }: { // account type toggle
  value: AccountType | null;
  onChange: (t: AccountType) => void;
  legend?: string;
  hint?: string;
}) {
  const options: { v: AccountType; title: string; text: string }[] = [
    { v: "seeker", title: "I'm looking for a home", text: "Search verified listings and book visits" },
    { v: "owner", title: "I'm renting out my home", text: "Get verified and list your property" },
  ];
  return (
    <fieldset className="mb-6">
      <legend className="mb-2 text-sm font-medium">{legend}</legend>
      {hint && <p className="-mt-1 mb-2 text-xs text-muted">{hint}</p>}
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map((o) => (
          <label
            key={o.v}
            className={`flex cursor-pointer flex-col gap-0.5 rounded-xl border p-3 text-sm transition-colors ${
              value === o.v ? "border-vault bg-vault-soft" : "border-line bg-surface hover:border-ink/30"
            }`}
          >
            <input
              type="radio"
              name="account-type"
              value={o.v}
              checked={value === o.v}
              onChange={() => {
                onChange(o.v);
              }}
              className="sr-only"
            />
            <span className={`font-medium ${value === o.v ? "text-vault" : "text-ink"}`}>{o.title}</span>
            <span className="text-xs text-muted">{o.text}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
