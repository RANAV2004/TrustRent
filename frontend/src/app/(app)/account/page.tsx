"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, apiMode } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { deleteSaved, listSaved, SavedSearch } from "@/lib/searches";

export default function AccountPage() { // account settings
  const { user, setEmailNotifications, signOut } = useAuth();
  const router = useRouter();
  const [saved, setSaved] = useState<SavedSearch[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [emailsOn, setEmailsOn] = useState<boolean | null>(null);
  useEffect(() => {
    if (apiMode) listSaved().then(setSaved, () => setSaved([]));
  }, []);
  if (!user) return null;
  async function toggle(on: boolean) {
    setError(null);
    setEmailsOn(on); // show the change straight away
    try {
      await setEmailNotifications(on);
    } catch (e) {
      setEmailsOn(!on);
      setError(e instanceof Error ? e.message : "Could not save.");
    }
  }
  async function everywhere() {
    if (!confirm("Sign out on every device, including this one?")) return;
    try {
      await api("/auth/logout-all", { method: "POST" });
    } finally {
      await signOut();
      router.replace("/login");
    }
  }
  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-3xl sm:text-4xl">Account</h1>
        <p className="text-muted">{user.firstName} {user.lastName} · {user.email}</p>
        <p className="text-xs text-muted">Your email is fixed once the account is created.</p>
      </div>
      <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
        <h2 className="text-lg">Email notifications</h2>
        <label className="flex items-start gap-3 text-sm">
          <input type="checkbox" className="mt-1 h-4 w-4 accent-vault" checked={emailsOn ?? user.emailNotifications !== false} onChange={(e) => toggle(e.target.checked)} />
          <span>Email me about new messages, visit answers, deposit settlements, disputes, agreements and saved-search alerts.
            <span className="block text-xs text-muted">Security emails (password changes) are always sent.</span></span>
        </label>
        {error && <p role="alert" className="text-sm text-claim">{error}</p>}
      </section>
      {apiMode && (
        <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
          <h2 className="text-lg">Saved searches</h2>
          {!saved ? <p className="text-sm text-muted">Loading...</p> : saved.length === 0 ? (
            <p className="text-sm text-muted">None yet. On a search results page, choose <strong>Save search &amp; alert me</strong>.</p>
          ) : (
            <ul className="flex flex-col divide-y divide-line">
              {saved.map((s) => (
                <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                  <Link href={`/search?q=${encodeURIComponent(s.filters.q)}`} className="font-medium text-vault hover:underline">{s.name}</Link>
                  <button type="button" onClick={() => deleteSaved(s.id).then(() => setSaved((l) => l!.filter((x) => x.id !== s.id)))}
                    className="text-xs text-muted hover:text-claim">Delete</button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
      <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
        <h2 className="text-lg">Security</h2>
        <div className="flex flex-wrap gap-3 text-sm">
          <Link href="/forgot-password" className="rounded-lg border border-line px-3 py-1.5 hover:border-ink/40">Change password</Link>
          {apiMode && <button type="button" onClick={everywhere} className="rounded-lg border border-line px-3 py-1.5 hover:border-ink/40">Sign out everywhere</button>}
        </div>
        {(user.isAdmin || user.isArbitrator) && (
          <p className="text-sm">Two-step sign-in: <strong>{user.mfaEnabled ? "on" : "set up at your next sign-in"}</strong></p>
        )}
      </section>
    </div>
  );
}
