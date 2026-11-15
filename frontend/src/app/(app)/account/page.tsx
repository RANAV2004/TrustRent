"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, apiMode } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { deleteSaved, listSaved, SavedSearch } from "@/lib/searches";
import { myPayout, PayoutAccount, savePayout } from "@/lib/trust";

function PayoutSection() { // owner bank details
  const [acc, setAcc] = useState<PayoutAccount | null | undefined>(undefined);
  const [edit, setEdit] = useState(false);
  const [f, setF] = useState({ holderName: "", ifsc: "", accountNumber: "", pan: "" });
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { myPayout().then((r) => setAcc(r.account), () => setAcc(null)); }, []);
  if (acc === undefined) return null;
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      setAcc((await savePayout(f)).account);
      setEdit(false);
      setF({ holderName: "", ifsc: "", accountNumber: "", pan: "" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save.");
    }
  }
  const field = "rounded-lg border border-line px-3 py-2";
  const STATUS = { submitted: "Being checked by TrustRent", active: "Verified", rejected: "Needs another look" };
  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
      <h2 className="text-lg">Payouts</h2>
      <p className="text-sm text-muted">Where TrustRent sends your rent and any deposit deductions. Your PAN appears on tenants&apos; rent receipts for their HRA claims.</p>
      {acc && !edit && (
        <div className="text-sm">
          <p>{acc.holderName} · {acc.ifsc} · account ending {acc.accountLast4} · PAN ending {acc.panLast4}</p>
          <p className={acc.status === "active" ? "text-vault" : acc.status === "rejected" ? "text-claim" : "text-amber"}>{STATUS[acc.status]}{acc.note ? `: ${acc.note}` : ""}</p>
          <button type="button" onClick={() => setEdit(true)} className="mt-2 text-vault hover:underline">Change bank details</button>
        </div>
      )}
      {(!acc || edit) && (
        <form onSubmit={save} className="grid gap-2 sm:grid-cols-2">
          <input placeholder="Account holder name" value={f.holderName} onChange={(e) => setF({ ...f, holderName: e.target.value })} className={field} aria-label="Account holder name" />
          <input placeholder="IFSC, e.g. HDFC0001234" value={f.ifsc} onChange={(e) => setF({ ...f, ifsc: e.target.value.toUpperCase() })} className={field} aria-label="IFSC" />
          <input placeholder="Account number" inputMode="numeric" value={f.accountNumber} onChange={(e) => setF({ ...f, accountNumber: e.target.value.replace(/\D/g, "") })} className={field} aria-label="Account number" />
          <input placeholder="PAN, e.g. ABCDE1234F" value={f.pan} onChange={(e) => setF({ ...f, pan: e.target.value.toUpperCase() })} className={field} aria-label="PAN" />
          {error && <p role="alert" className="text-sm text-claim sm:col-span-2">{error}</p>}
          <button type="submit" className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep">Save bank details</button>
        </form>
      )}
      <p className="text-xs text-muted">Account number and PAN are encrypted. Changing the bank account sends it for a fresh check before money goes there.</p>
    </section>
  );
}

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
      {apiMode && user.accountType === "owner" && <PayoutSection />}
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
