"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode } from "react";
import { AdminShell } from "@/components/admin-shell";
import { Wordmark } from "@/components/wordmark";
import { PremiumBadge } from "@/components/listing-ui";
import { apiMode } from "@/lib/api";
import { isPremium } from "@/lib/auth";
import { homeFor, useAuth } from "@/lib/auth-context";
import { useStore } from "@/lib/local-store";
import { unreadCount } from "@/lib/messages";
import { ApiSync } from "@/lib/sync";
export function Logo() { // logo
  return (
    <Link href="/" className="flex items-center gap-2">
      <svg width="28" height="28" viewBox="0 0 40 40" aria-hidden="true">
        <rect x="2" y="2" width="36" height="36" rx="10" fill="var(--vault)" />
        <path d="M9 20 20 11l11 9" fill="none" stroke="white" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M14 24.5l4 4 8-8" fill="none" stroke="#e8a33d" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <Wordmark />
    </Link>
  );
}
export function AppShell({ children }: { children: ReactNode }) { // app shell
  const { user, signOut, setAccountType } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const unread = useStore(() => (user ? unreadCount(user.id) : 0), [user?.id]);
  const owner = user?.accountType === "owner";
  const main: { href: string; label: string; active: boolean; badge?: boolean; count?: number }[] = owner
    ? [
        { href: "/owner", label: "Dashboard", active: pathname === "/owner" || pathname.startsWith("/owner/verify") },
        { href: "/owner/listings/new", label: "Add listing", active: pathname.startsWith("/owner/listings") },
        { href: "/messages", label: "Messages", active: pathname.startsWith("/messages"), count: unread },
        { href: "/deposits", label: "Deposits", active: pathname.startsWith("/deposits") },
      ]
    : [
        { href: "/search", label: "Search homes", active: pathname.startsWith("/search") || pathname.startsWith("/listings") },
        { href: "/agent", label: "HomePref AI", active: pathname.startsWith("/agent"), badge: true },
        { href: "/messages", label: "Messages", active: pathname.startsWith("/messages"), count: unread },
        { href: "/deposits", label: "Deposits", active: pathname.startsWith("/deposits") },
        { href: "/premium", label: "Premium", active: pathname.startsWith("/premium") },
      ];
  async function switchType() {
    if (!user) return;
    const u = await setAccountType(owner ? "seeker" : "owner");
    router.push(homeFor(u));
  }
  if (user?.isAdmin) return <AdminShell>{children}</AdminShell>;
  const initials = user ? `${user.firstName[0] ?? ""}${user.lastName[0] ?? ""}`.toUpperCase() : "";
  return (
    <div className="flex min-h-dvh flex-col">
      {user && <ApiSync userId={user.id} />}
      <header className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <Logo />
          <nav className="flex flex-wrap gap-1 text-sm" aria-label="Main">
            {main.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                aria-current={item.active ? "page" : undefined}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 ${item.active ? "bg-vault-soft font-medium text-vault" : "text-muted hover:text-ink"}`}
              >
                {item.badge && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <path d="M12 3l1.8 4.6L18 9l-4.2 1.4L12 15l-1.8-4.6L6 9l4.2-1.4z" /><path d="M18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" />
                  </svg>
                )}
                {item.label}
                {!!item.count && (
                  <span className="grid h-5 min-w-5 place-items-center rounded-full bg-vault px-1 text-[11px] font-semibold text-white" aria-label={`${item.count} unread`}>
                    {item.count}
                  </span>
                )}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            {user && (
              <>
                <span className="hidden items-center gap-2 text-sm md:flex">
                  <span className="grid h-8 w-8 place-items-center rounded-full bg-vault-soft text-xs font-semibold text-vault" aria-hidden="true">{initials}</span>
                  <span className="flex flex-col leading-tight">
                    <span className="flex items-center gap-1.5 font-medium">{user.firstName} {user.lastName}{isPremium(user) && <PremiumBadge small />}</span>
                    <span className="text-xs text-muted">@{user.username} · {owner ? "Owner" : "Looking for a home"}</span>
                  </span>
                </span>
                <button
                  onClick={switchType}
                  className="rounded-md px-2 py-1.5 text-sm text-vault hover:underline"
                  title={owner ? "Switch to looking for a home" : "Switch to renting out a home"}
                >
                  {owner ? "I'm looking for a home" : "Rent out my home"}
                </button>
                <button
                  onClick={() => signOut().then(() => router.replace("/login"))}
                  className="rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:border-ink/40 hover:text-ink"
                >
                  Sign out
                </button>
              </>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-10">{children}</main>
      <footer className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-6 text-xs text-muted sm:px-6">
        <span>© {new Date().getFullYear()} TrustRent · {apiMode ? "Deposits are receipted on a tamper-proof ledger." : "Demo mode: data stays in this browser."}</span>
        <nav className="flex gap-4" aria-label="Legal">
          <Link href="/privacy" className="hover:text-ink hover:underline">Privacy Policy</Link>
          <Link href="/terms" className="hover:text-ink hover:underline">Terms of Use</Link>
        </nav>
      </footer>
    </div>
  );
}
