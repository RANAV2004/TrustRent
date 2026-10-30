import Link from "next/link";
import { ReactNode } from "react";
import { Logo } from "@/components/app-shell";
export const LEGAL_UPDATED = "29 October 2026";
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "";
export const GRIEVANCE_OFFICER = process.env.NEXT_PUBLIC_GRIEVANCE_OFFICER || "";
export function Contact() { // contact
  return CONTACT_EMAIL ? <a href={`mailto:${CONTACT_EMAIL}`} className="text-vault underline">{CONTACT_EMAIL}</a> : <strong>the contact email listed on this page</strong>;
}
export function LegalPage({ title, children }: { title: string; children: ReactNode }) { // legal page
  return (
    <div className="min-h-dvh bg-mist">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3 sm:px-6">
          <Logo />
          <nav className="flex gap-4 text-sm text-muted">
            <Link href="/privacy" className="hover:text-ink">Privacy</Link>
            <Link href="/terms" className="hover:text-ink">Terms</Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10 sm:px-6 [&_h2]:mt-4 [&_h2]:text-xl [&_li]:ml-5 [&_li]:list-disc [&_p]:leading-relaxed [&_ul]:flex [&_ul]:flex-col [&_ul]:gap-1.5">
        <div>
          <h1 className="text-3xl sm:text-4xl">{title}</h1>
          <p className="mt-1 text-sm text-muted">Last updated {LEGAL_UPDATED}</p>
        </div>
        {children}
      </main>
    </div>
  );
}
