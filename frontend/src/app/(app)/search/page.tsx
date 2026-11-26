"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useMemo, useState } from "react";
import { ListingCard } from "@/components/listing-ui";
import { isPremium } from "@/lib/auth";
import { useAuth } from "@/lib/auth-context";
import {
  activeFilterCount, allListings, AMENITY_LABEL, applyFilters, EMPTY_FILTERS, Filters, Furnishing,
  searchListings, SORT_LABEL, SortKey, sortListings, TENANT_LABEL, TenantType,
} from "@/lib/listings";
import { useStore } from "@/lib/local-store";
import { apiReady } from "@/lib/sync";
function Hero({ name }: { name?: string }) {
  return (
    <section className="relative isolate flex min-h-[calc(100dvh-16rem)] flex-col justify-center overflow-hidden rounded-3xl border border-line bg-mist px-5 py-14 sm:px-10 lg:px-16">
      <div aria-hidden="true" className="absolute inset-0 -z-20 bg-cover bg-position-[center_55%] opacity-25 lg:left-auto lg:w-[58%] lg:opacity-100"
        style={{ backgroundImage: "url(/keys-bg.jpg)" }} />
      <div aria-hidden="true" className="absolute inset-0 -z-10 bg-mist/60 lg:left-auto lg:w-[58%] lg:bg-transparent lg:bg-linear-to-r lg:from-mist lg:via-mist/60 lg:via-25% lg:to-transparent lg:to-55%" />
      <div className="w-full max-w-xl text-center lg:text-left">
        <h1 className="text-3xl sm:text-5xl">Hi {name}, where are you looking?</h1>
        <p className="mt-3 text-muted">Search by city, area or 6-digit pin code. Every owner here is identity-verified.</p>
        <div className="mt-8"><SearchBox initial="" /></div>
      </div>
    </section>
  );
}
function SearchBox({ initial }: { initial: string }) {
  const router = useRouter();
  const [q, setQ] = useState(initial);
  function submit(e: FormEvent) {
    e.preventDefault();
    if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
  }
  return (
    <form onSubmit={submit} role="search" className="flex flex-col gap-2 sm:flex-row">
      <label htmlFor="q" className="sr-only">City, area or pin code</label>
      <div className="relative flex-1">
        <svg className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-muted" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
        </svg>
        <input
          id="q"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="City, area or pin code, e.g. Indore, Vijay Nagar or 452010"
          className="w-full rounded-xl border border-line bg-surface py-3.5 pr-4 pl-10 text-[15px] focus:border-vault focus:ring-2 focus:ring-vault/20 focus:outline-none"
        />
      </div>
      <button type="submit" className="rounded-xl bg-vault px-6 py-3.5 text-[15px] font-medium text-white hover:bg-vault-deep">
        Search
      </button>
    </form>
  );
}
function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 py-1 text-sm">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 accent-vault" />
      {label}
    </label>
  );
}
function toggle<T>(list: T[], v: T, on: boolean) {
  return on ? [...list, v] : list.filter((x) => x !== v);
}
function FilterPanel({ f, set }: { f: Filters; set: (f: Filters) => void }) {
  const num = (v: string) => (v === "" ? null : Math.max(0, Number(v)));
  return (
    <div className="flex flex-col gap-5 text-sm">
      <fieldset>
        <legend className="mb-2 font-semibold">Monthly rent (₹)</legend>
        <div className="flex items-center gap-2">
          <label className="sr-only" htmlFor="bmin">Minimum rent</label>
          <input id="bmin" type="number" inputMode="numeric" placeholder="Min" value={f.budgetMin ?? ""} onChange={(e) => set({ ...f, budgetMin: num(e.target.value) })} className="w-full rounded-lg border border-line px-2.5 py-2" />
          <span className="text-muted">to</span>
          <label className="sr-only" htmlFor="bmax">Maximum rent</label>
          <input id="bmax" type="number" inputMode="numeric" placeholder="Max" value={f.budgetMax ?? ""} onChange={(e) => set({ ...f, budgetMax: num(e.target.value) })} className="w-full rounded-lg border border-line px-2.5 py-2" />
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-1 font-semibold">Bedrooms</legend>
        <div className="flex gap-2">
          {[1, 2, 3].map((b) => {
            const on = f.bhk.includes(b);
            return (
              <button key={b} type="button" aria-pressed={on} onClick={() => set({ ...f, bhk: toggle(f.bhk, b, !on) })}
                className={`flex-1 rounded-lg border px-2 py-2 ${on ? "border-vault bg-vault-soft font-medium text-vault" : "border-line hover:border-ink/30"}`}>
                {b === 3 ? "3+ BHK" : `${b} BHK`}
              </button>
            );
          })}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-1 font-semibold">Furnishing</legend>
        {(["furnished", "semi-furnished", "unfurnished"] as Furnishing[]).map((x) => (
          <Check key={x} label={x[0].toUpperCase() + x.slice(1)} checked={f.furnishing.includes(x)} onChange={(on) => set({ ...f, furnishing: toggle(f.furnishing, x, on) })} />
        ))}
      </fieldset>
      <fieldset>
        <legend className="mb-1 font-semibold">Facilities</legend>
        <div className="grid grid-cols-2 gap-x-2 lg:grid-cols-1">
          {Object.entries(AMENITY_LABEL).map(([k, label]) => (
            <Check key={k} label={label} checked={f.amenities.includes(k)} onChange={(on) => set({ ...f, amenities: toggle(f.amenities, k, on) })} />
          ))}
        </div>
      </fieldset>
      <div>
        <label htmlFor="tenant" className="mb-1 block font-semibold">Who will live there</label>
        <select id="tenant" value={f.tenantType} onChange={(e) => set({ ...f, tenantType: e.target.value as TenantType | "" })} className="w-full rounded-lg border border-line px-2.5 py-2">
          <option value="">Anyone</option>
          {(["family", "bachelor_male", "bachelor_female", "student"] as TenantType[]).map((t) => (
            <option key={t} value={t}>{TENANT_LABEL[t]}</option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="avail" className="mb-1 block font-semibold">Move in by</label>
        <input id="avail" type="date" value={f.availableBy} onChange={(e) => set({ ...f, availableBy: e.target.value })} className="w-full rounded-lg border border-line px-2.5 py-2" />
      </div>
      <fieldset>
        <legend className="mb-1 font-semibold">Deposit and trust</legend>
        <Check label="Deposit 2 months or less" checked={f.depositWithinCap} onChange={(v) => set({ ...f, depositWithinCap: v })} />
        <Check label="Owner has a TrustRent track record" checked={f.withHistory} onChange={(v) => set({ ...f, withHistory: v })} />
      </fieldset>
    </div>
  );
}
function Results() {
  const q = useSearchParams().get("q") ?? "";
  const { user } = useAuth();
  const premium = isPremium(user);
  const all = useStore(allListings);
  const ready = useStore(apiReady);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [sort, setSort] = useState<SortKey>("recommended");
  const [showFilters, setShowFilters] = useState(false);
  const match = useMemo(() => searchListings(q, all), [q, all]);
  const shown = useMemo(() => sortListings(applyFilters(match.results, filters), sort), [match, filters, sort]);
  const nFilters = activeFilterCount(filters);
  return (
    <div className="flex flex-col gap-6">
      {!q ? <Hero name={user?.firstName} /> : <SearchBox key={q} initial={q} />}
      {q && !ready ? (
        <p className="text-sm text-muted" role="status">Loading homes…</p>
      ) : !q ? null : (
        <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
          <aside className={`${showFilters ? "block" : "hidden"} rounded-2xl border border-line bg-surface p-5 lg:block lg:self-start`} aria-label="Filters">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base">Filters</h2>
              {nFilters > 0 && (
                <button type="button" onClick={() => setFilters(EMPTY_FILTERS)} className="text-sm text-vault hover:underline">Clear all</button>
              )}
            </div>
            <FilterPanel f={filters} set={setFilters} />
          </aside>
          <section className="flex min-w-0 flex-col gap-4" aria-live="polite">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm">
                {match.kind === "none" ? (
                  <>No area matches <strong>&ldquo;{match.label}&rdquo;</strong>. Try Indore, Vijay Nagar, Pipliyahana or a pin code like 452010.</>
                ) : (
                  <><strong className="text-base">{shown.length}</strong> home{shown.length === 1 ? "" : "s"} in {match.label}{nFilters ? ` · ${nFilters} filter${nFilters > 1 ? "s" : ""}` : ""}</>
                )}
              </p>
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => setShowFilters((s) => !s)} className="rounded-lg border border-line bg-surface px-3 py-2 text-sm lg:hidden">
                  {showFilters ? "Hide filters" : `Filters${nFilters ? ` (${nFilters})` : ""}`}
                </button>
                <label htmlFor="sort" className="text-sm text-muted">Sort</label>
                <select id="sort" value={sort} onChange={(e) => setSort(e.target.value as SortKey)} className="rounded-lg border border-line bg-surface px-2.5 py-2 text-sm">
                  {Object.entries(SORT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
            </div>
            {match.kind !== "none" && shown.length === 0 && (
              <div className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">
                No homes match these filters. <button type="button" onClick={() => setFilters(EMPTY_FILTERS)} className="text-vault hover:underline">Clear filters</button> to see more homes.
              </div>
            )}
            <ul className="flex flex-col gap-4">
              {shown.map((l) => (
                <li key={l.id}><ListingCard l={l} premium={premium} /></li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}
export default function SearchPage() { // search
  return (
    <Suspense>
      <Results />
    </Suspense>
  );
}
