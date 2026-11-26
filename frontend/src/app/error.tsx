"use client";
import Link from "next/link";
import { useEffect } from "react";
import { reportError } from "@/lib/report-error";

export default function ErrorPage({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) { // page crash
  useEffect(() => { reportError(error, error.digest); }, [error]);
  return (
    <main className="mx-auto flex min-h-[60dvh] max-w-md flex-col items-start justify-center gap-4 px-4">
      <h1 className="text-2xl">Something went wrong</h1>
      <p className="text-sm text-muted">This page hit a problem. We&apos;ve been told about it. Your data is safe: try again, or go back to the start.</p>
      <div className="flex gap-3">
        <button type="button" onClick={() => retry()} className="rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep">Try again</button>
        <Link href="/" className="rounded-lg border border-line px-4 py-2 text-sm hover:border-ink/40">Go to the start</Link>
      </div>
    </main>
  );
}
