"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { Wordmark } from "@/components/wordmark";
import { useAuth } from "@/lib/auth-context";
const ALLOWED_OUTSIDE = ["/listings/", "/deposits/lookup"];
const NAV: { href: string; label: string; icon: string }[] = [
  { href: "/admin", label: "Overview", icon: "M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z" },
  { href: "/admin/users", label: "Users", icon: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" },
  { href: "/admin/listings", label: "Listings", icon: "M3 10.5 12 3l9 7.5V21H3zM9 21v-6h6v6" },
  { href: "/admin/messages", label: "Messages", icon: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" },
  { href: "/admin/deposits", label: "Deposits & receipts", icon: "M4 7h16v13H4zM8 7V4h8v3M9 13l2 2 4-4" },
  { href: "/admin/premium", label: "Premium", icon: "M12 2l3 6.5 7 .8-5.2 4.8 1.4 7L12 17.6 5.8 21l1.4-7L2 9.3l7-.8z" },
  { href: "/admin/verifications", label: "Verifications", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10zM9 12l2 2 4-4" },
];
function Mark() {
  return (
    <svg width="26" height="26" viewBox="0 0 40 40" aria-hidden="true">
      <rect x="2" y="2" width="36" height="36" rx="10" fill="#2f9e82" />
      <path d="M9 20 20 11l11 9" fill="none" stroke="white" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M14 24.5l4 4 8-8" fill="none" stroke="#e8a33d" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function Icon({ d }: { d: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}
export function AdminShell({ children }: { children: ReactNode }) { // admin shell
  const { user, signOut } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const inside = pathname.startsWith("/admin") || ALLOWED_OUTSIDE.some((p) => pathname.startsWith(p));
  useEffect(() => {
    if (!inside) router.replace("/admin");
  }, [inside, router]);
  const active = (href: string) => (href === "/admin" ? pathname === "/admin" : pathname.startsWith(href));
  const nav = (
    <nav className="flex flex-col gap-1" aria-label="Admin">
      {NAV.map((n) => (
        <Link key={n.href} href={n.href} onClick={() => setOpen(false)} aria-current={active(n.href) ? "page" : undefined}
          className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${active(n.href) ? "bg-white/15 font-medium text-white" : "text-white/70 hover:bg-white/10 hover:text-white"}`}>
          <Icon d={n.icon} />
          {n.label}
        </Link>
      ))}
    </nav>
  );
  return (
    <div className="min-h-dvh bg-[#f4f6f5] lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
      <aside className="hidden flex-col gap-6 bg-vault-deep px-4 py-6 text-white lg:sticky lg:top-0 lg:flex lg:h-dvh">
        <div className="px-3">
          <p className="flex items-center gap-2 [--logo-rent:#5cc4a6]"><Mark /><Wordmark /></p>
          <p className="text-xs tracking-wide text-white/60 uppercase">Admin console</p>
        </div>
        {nav}
        <div className="mt-auto flex flex-col gap-2 border-t border-white/15 px-3 pt-4 text-sm">
          <span className="font-medium">{user?.firstName} {user?.lastName}</span>
          <span className="truncate text-xs text-white/60">{user?.email}</span>
          <button type="button" onClick={() => signOut().then(() => router.replace("/login"))}
            className="mt-1 w-fit rounded-md border border-white/30 px-3 py-1.5 text-xs hover:bg-white/10">Sign out</button>
        </div>
      </aside>
      <header className="sticky top-0 z-20 flex items-center justify-between bg-vault-deep px-4 py-3 text-white lg:hidden">
        <span className="flex items-center gap-2 [--logo-rent:#5cc4a6]"><Mark /><Wordmark className="text-xl" /> <span className="text-sm font-normal text-white/60">Admin</span></span>
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="rounded-md border border-white/30 px-3 py-1.5 text-sm">
          {open ? "Close" : "Menu"}
        </button>
      </header>
      {open && (
        <div className="flex flex-col gap-4 bg-vault-deep px-4 pb-4 text-white lg:hidden">
          {nav}
          <button type="button" onClick={() => signOut().then(() => router.replace("/login"))}
            className="w-fit rounded-md border border-white/30 px-3 py-1.5 text-xs">Sign out</button>
        </div>
      )}
      <main className="min-w-0 px-4 py-6 sm:px-8 sm:py-8">{inside ? children : null}</main>
    </div>
  );
}
