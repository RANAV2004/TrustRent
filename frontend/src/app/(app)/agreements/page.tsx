"use client";
import { useEffect, useState } from "react";
import { apiMode } from "@/lib/api";
import { downloadAgreement, fileSize, SharedAgreement, sharedWithMe } from "@/lib/legal";

export default function AgreementsPage() { // tenant agreements
  const [docs, setDocs] = useState<SharedAgreement[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (apiMode) sharedWithMe().then(setDocs, (e) => setError(e.message));
  }, []);
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl">Agreements</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">Rental agreements that owners have shared with you. Each one was prepared by a TrustRent-verified lawyer.</p>
      </div>
      {!apiMode ? <p className="text-sm text-muted">Agreements need the TrustRent server. They aren&apos;t available in this demo.</p>
        : error ? <p role="alert" className="text-sm text-claim">{error}</p>
        : !docs ? <p className="text-sm text-muted">Loading...</p>
        : !docs.length ? (
          <p className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">No agreements yet. When your owner shares one, it appears here.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {docs.map((d) => (
              <li key={d.id} className="flex flex-col gap-2 rounded-2xl border border-line bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="font-medium">{d.title}</p>
                  <p className="text-sm text-muted">{d.listing ?? "Rental agreement"} · from {d.owner} · prepared by {d.lawyer}</p>
                  <p className="text-xs text-muted">{d.fileName} · {fileSize(d.size)} · shared {new Date(d.sharedAt).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</p>
                  <p className="text-[11px] break-all text-muted">Fingerprint {d.fileHash}</p>
                </div>
                <button type="button" onClick={() => downloadAgreement(d).catch((e) => setError(e.message))}
                  className="shrink-0 rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep">Download PDF</button>
              </li>
            ))}
          </ul>
        )}
      <p className="text-xs text-muted">Read the agreement before you sign. Print it and sign it with your owner; ask them about stamp duty and registration.</p>
    </div>
  );
}
