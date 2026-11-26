"use client";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { FormError, PasswordField, SubmitButton } from "@/components/auth-ui";
import { AuthError } from "@/lib/auth";
import { useAuth } from "@/lib/auth-context";
import { CaseSummary, getCases } from "@/lib/legal";

function ChangePassword({ firstTime }: { firstTime: boolean }) {
  const { changePassword } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    if (next !== again) return setErrors({ again: "The two new passwords don't match." });
    setErrors({});
    setBusy(true);
    try {
      await changePassword(current, next);
      setCurrent(""); setNext(""); setAgain("");
      setSaved(true);
    } catch (err) {
      if (err instanceof AuthError && err.field) setErrors({ [err.field]: err.message });
      else setError(err instanceof AuthError ? err.message : "Couldn't change the password. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="flex max-w-md flex-col gap-4 rounded-2xl border border-line bg-surface p-5" noValidate>
      <div>
        <h2 className="text-lg">{firstTime ? "Choose your own password" : "Change password"}</h2>
        {firstTime && <p className="mt-1 text-sm text-muted">You signed in with the temporary password we sent you. Choose a new one to open your portal.</p>}
      </div>
      <PasswordField id="current" label={firstTime ? "Temporary password" : "Current password"} autoComplete="current-password"
        value={current} onChange={(e) => setCurrent(e.target.value)} error={errors.currentPassword} />
      <PasswordField id="new" label="New password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)}
        error={errors.newPassword} hint="At least 8 characters, with a letter and a number." />
      <PasswordField id="again" label="New password again" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} error={errors.again} />
      <FormError message={error} />
      {saved && <p role="status" className="text-sm text-vault">Password changed. Other devices were signed out.</p>}
      <SubmitButton busy={busy}>{busy ? "Saving..." : "Save password"}</SubmitButton>
    </form>
  );
}

export default function LawyerPortal() { // lawyer portal
  const { user } = useAuth();
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const mustChange = !!user?.mustChangePassword;
  const load = useCallback(() => { getCases().then(setCases, (e) => setError(e.message)); }, []);
  useEffect(() => {
    if (mustChange) return;
    load();
    const t = window.setInterval(() => { if (document.visibilityState === "visible") load(); }, 15000);
    return () => window.clearInterval(t);
  }, [load, mustChange]);
  if (!user) return null;
  if (mustChange) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-3xl">Welcome, {user.firstName}</h1>
        <ChangePassword firstTime />
      </div>
    );
  }
  const unread = cases?.reduce((n, c) => n + c.unread, 0) ?? 0;
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl">Agreement requests</h1>
          <p className="mt-1 text-sm text-muted">Owners who want you to prepare their rental agreement. Reply here and upload the finished agreement as a PDF.</p>
        </div>
        <button type="button" onClick={() => setShowPassword((s) => !s)} className="rounded-lg border border-line px-3 py-2 text-sm hover:border-ink/40">
          {showPassword ? "Close" : "Change password"}
        </button>
      </div>
      {showPassword && <ChangePassword firstTime={false} />}
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
      {!cases ? <p className="text-sm text-muted">Loading...</p> : !cases.length ? (
        <div className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">
          No requests yet. Owners on TrustRent can find you in the lawyer directory and message you here.
        </div>
      ) : (
        <section className="flex flex-col gap-3">
          <p className="text-sm text-muted">{cases.length} request{cases.length === 1 ? "" : "s"}{unread ? `, ${unread} unread message${unread === 1 ? "" : "s"}` : ""}</p>
          <ul className="flex flex-col gap-3">
            {cases.map((c) => (
              <li key={c.id}>
                <Link href={`/legal/${c.id}`} className="flex flex-col gap-1 rounded-2xl border border-line bg-surface p-4 hover:border-ink/30 sm:flex-row sm:items-center sm:justify-between">
                  <span className="min-w-0">
                    <span className="flex items-center gap-2 font-medium">
                      {c.owner.name}
                      {c.unread > 0 && <span className="rounded-full bg-vault px-2 py-0.5 text-[11px] font-semibold text-white">{c.unread} new</span>}
                    </span>
                    <span className="block text-sm text-muted">{c.listing ? `${c.listing.title}, ${c.listing.area}` : c.subject}</span>
                    <span className="block truncate text-sm">{c.lastMessage}</span>
                  </span>
                  <span className="shrink-0 text-xs text-muted">
                    {c.agreements} document{c.agreements === 1 ? "" : "s"} · {new Date(c.updatedAt).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
