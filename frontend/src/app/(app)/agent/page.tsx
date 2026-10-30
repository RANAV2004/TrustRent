import Link from "next/link";
export default function AgentPage() { // homepref ai
  return (
    <div className="flex flex-col items-center gap-5 py-16 text-center">
      <span className="grid h-14 w-14 place-items-center rounded-2xl bg-vault-soft text-vault" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 3l1.8 4.6L18 9l-4.2 1.4L12 15l-1.8-4.6L6 9l4.2-1.4z" />
          <path d="M18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" />
        </svg>
      </span>
      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium text-vault">HomePref AI</p>
        <h1 className="text-3xl sm:text-4xl">Will be updated shortly</h1>
        <p className="max-w-lg text-muted">
          HomePref is our AI assistant that will understand what you need (budget, area, size and facilities) and find the
          TrustRent homes that fit best. It&apos;s on its way.
        </p>
      </div>
      <Link href="/search" className="rounded-lg bg-vault px-5 py-2.5 text-sm font-medium text-white hover:bg-vault-deep">
        Search homes for now
      </Link>
    </div>
  );
}
