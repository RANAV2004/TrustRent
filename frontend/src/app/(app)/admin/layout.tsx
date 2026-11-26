"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { TwoFactorSetup } from "@/components/two-factor-setup";
import { apiMode } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useAuth();
  const router = useRouter();
  const [skipped, setSkipped] = useState(false);
  if (!apiMode || !user?.isAdmin) {
    return <p className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">The admin console is only for TrustRent admins{apiMode ? "" : " and needs the backend"}.</p>;
  }
  const tf = user.twoFactor;
  if (tf?.enabled && !tf.verified) { // a session from before two-step sign-in was turned on
    return (
      <section className="mx-auto flex max-w-md flex-col gap-3 rounded-2xl border border-line bg-surface p-6">
        <h1 className="text-xl">Sign in again</h1>
        <p className="text-sm text-muted">This session didn&apos;t use your authenticator code. Sign in again to open the admin console.</p>
        <button type="button" onClick={() => signOut().then(() => router.replace("/login?next=/admin"))}
          className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white">Sign in again</button>
      </section>
    );
  }
  if (tf && !tf.enabled && (tf.required || !skipped)) {
    return (
      <div className="flex flex-col gap-3">
        <TwoFactorSetup required={tf.required} onFinished={() => setSkipped(true)} />
        {!tf.required && (
          <button type="button" onClick={() => setSkipped(true)} className="mx-auto text-sm text-muted hover:text-ink">Not now</button>
        )}
      </div>
    );
  }
  return <>{children}</>;
}
