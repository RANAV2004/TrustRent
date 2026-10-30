"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChangeEvent, FormEvent, ReactNode, useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatINR } from "@/lib/format";
import { AMENITY_LABEL, Furnishing, TENANT_LABEL, TenantType } from "@/lib/listings";
import { StorageFullError, useStore } from "@/lib/local-store";
import { compressImage, createOwnerListing, getApplication, parseMapsLink } from "@/lib/owner";
const MAX_PHOTOS = 8;
const CITY_OPTIONS = ["Indore", "Bengaluru", "Pune", "Bhopal", "Mumbai", "Delhi", "Hyderabad", "Other"];
function Section({ n, title, hint, children }: { n: number; title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-5 sm:p-6">
      <div>
        <h2 className="text-lg"><span className="text-muted">{n}.</span> {title}</h2>
        {hint && <p className="text-sm text-muted">{hint}</p>}
      </div>
      {children}
    </section>
  );
}
function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium">{label}</span>
      {children}
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </label>
  );
}
const input = "rounded-lg border border-line px-3 py-2.5 focus:border-vault focus:outline-none";
export default function NewListing() { // add listing
  const { user } = useAuth();
  const router = useRouter();
  const uidv = user?.id ?? "";
  const app = useStore(() => getApplication(uidv), [uidv]);
  const [f, setF] = useState({
    title: "", address: "", locality: "", city: "Indore", pincode: "",
    rent: "", deposit: "", bhk: "2", furnishing: "semi-furnished" as Furnishing, area_sqft: "",
    available_from: new Date().toISOString().slice(0, 10), min_months: "11", max_months: "22",
    description: "", about_owner: "",
  });
  const [amenities, setAmenities] = useState<string[]>([]);
  const [tenants, setTenants] = useState<TenantType[]>(["any"]);
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [mapsText, setMapsText] = useState("");
  const [exact, setExact] = useState(false);
  const [photos, setPhotos] = useState<string[]>([]);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  if (!user) return null;
  if (app?.status !== "approved") {
    return (
      <div className="flex max-w-xl flex-col gap-3">
        <h1 className="text-3xl">Add a listing</h1>
        <p className="text-muted">You need to be a verified owner before your home can go live. It takes one ID document and one property document.</p>
        <Link href="/owner/verify" className="w-fit rounded-lg bg-vault px-4 py-2.5 text-sm font-medium text-white hover:bg-vault-deep">
          {app ? "Check verification status" : "Start verification"}
        </Link>
      </div>
    );
  }
  const set = (k: keyof typeof f) => (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const rent = Number(f.rent) || 0;
  const deposit = Number(f.deposit) || 0;
  const depMonths = rent ? Math.round((deposit / rent) * 10) / 10 : 0;
  function toggle<T>(list: T[], v: T): T[] {
    return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
  }
  function locateMe() {
    setMsg(null);
    if (!navigator.geolocation) return setMsg("Your browser can't share location. Paste a Google Maps link instead.");
    navigator.geolocation.getCurrentPosition(
      (p) => setCoords({ lat: +p.coords.latitude.toFixed(6), lng: +p.coords.longitude.toFixed(6) }),
      () => setMsg("Location permission was denied. Paste a Google Maps link instead."),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }
  function readMapsLink() {
    const c = parseMapsLink(mapsText);
    if (c) {
      setCoords(c);
      setMsg(null);
    } else {
      setMsg("Couldn't find coordinates in that link. In Google Maps, long-press your building, then copy the coordinates shown (like 22.7533, 75.8937) and paste them here.");
    }
  }
  async function addPhotos(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []).slice(0, MAX_PHOTOS - photos.length);
    e.target.value = "";
    if (!files.length) return;
    setPhotoBusy(true);
    setError(null);
    try {
      const out = await Promise.all(files.map((file) => compressImage(file)));
      setPhotos((p) => [...p, ...out].slice(0, MAX_PHOTOS));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read a photo.");
    } finally {
      setPhotoBusy(false);
    }
  }
  function move(i: number, d: -1 | 1) {
    const j = i + d;
    if (j < 0 || j >= photos.length) return;
    const p = [...photos];
    [p[i], p[j]] = [p[j], p[i]];
    setPhotos(p);
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const min = Number(f.min_months);
    const max = Number(f.max_months);
    const problems = [
      f.title.trim().length < 8 && "Give the listing a title of at least 8 characters.",
      (!f.address.trim() || !f.locality.trim()) && "Enter the address and locality.",
      !/^\d{6}$/.test(f.pincode) && "Enter a 6-digit pin code.",
      !coords && "Set the location on the map: use your current location or paste a Google Maps link.",
      rent < 1000 && "Enter the monthly rent.",
      deposit < 0 && "Deposit can't be negative.",
      !(min >= 1 && max >= min) && "Maximum stay must be at least the minimum stay.",
      !photos.length && "Add at least one photo of the home.",
      f.description.trim().length < 30 && "Describe the home in at least 30 characters.",
    ].filter(Boolean) as string[];
    if (problems.length) {
      setError(problems[0]);
      return;
    }
    try {
      setSaving(true);
      const l = await createOwnerListing(user!, {
        title: f.title.trim(), address: f.address.trim(), locality: f.locality.trim(), city: f.city, pincode: f.pincode,
        lat: coords!.lat, lng: coords!.lng, show_exact_location: exact,
        rent, deposit, bhk: Number(f.bhk), furnishing: f.furnishing, area_sqft: Number(f.area_sqft) || 0,
        amenities, preferred_tenants: tenants.length ? tenants : ["any"], available_from: f.available_from,
        min_months: min, max_months: max, description: f.description.trim(), about_owner: f.about_owner.trim(), photos,
      });
      router.push(`/listings/${l.id}`);
    } catch (err) {
      setSaving(false);
      setError(err instanceof StorageFullError
        ? "Your browser's storage is full (the demo keeps photos in the browser). Remove a few photos or delete an old listing and try again."
        : err instanceof ApiError ? err.message : "Couldn't save the listing. Try again.");
    }
  }
  const mapSrc = coords ? `https://maps.google.com/maps?q=${coords.lat},${coords.lng}&z=16&output=embed` : null;
  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <div>
        <Link href="/owner" className="text-sm text-muted hover:text-ink">Back to owner dashboard</Link>
        <h1 className="mt-2 text-3xl sm:text-4xl">List your home</h1>
        <p className="text-muted">New listings are shown to Premium members first for 48 hours, then to everyone.</p>
      </div>
      <Section n={1} title="Photos" hint={`Up to ${MAX_PHOTOS}. The first photo is the cover. Bright, wide shots of every room work best.`}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {photos.map((src, i) => (
            <figure key={i} className="group relative overflow-hidden rounded-xl border border-line">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={src} alt={`Photo ${i + 1}`} className="aspect-[4/3] w-full object-cover" />
              {i === 0 && <figcaption className="absolute top-1.5 left-1.5 rounded bg-black/60 px-1.5 text-[11px] text-white">Cover</figcaption>}
              <div className="absolute inset-x-0 bottom-0 flex justify-between bg-black/55 px-1.5 py-1 text-xs text-white">
                <span className="flex gap-1">
                  <button type="button" onClick={() => move(i, -1)} aria-label={`Move photo ${i + 1} left`} className="px-1">Left</button>
                  <button type="button" onClick={() => move(i, 1)} aria-label={`Move photo ${i + 1} right`} className="px-1">Right</button>
                </span>
                <button type="button" onClick={() => setPhotos(photos.filter((_, j) => j !== i))} aria-label={`Remove photo ${i + 1}`} className="px-1">Remove</button>
              </div>
            </figure>
          ))}
          {photos.length < MAX_PHOTOS && (
            <label className="grid aspect-[4/3] cursor-pointer place-items-center rounded-xl border-2 border-dashed border-line text-center text-sm text-muted hover:border-vault hover:text-vault">
              <input type="file" accept="image/*" multiple onChange={addPhotos} className="sr-only" />
              {photoBusy ? "Adding..." : <span>+ Add photos<br /><span className="text-xs">{photos.length}/{MAX_PHOTOS}</span></span>}
            </label>
          )}
        </div>
      </Section>
      <Section n={2} title="The home">
        <Field label="Listing title"><input value={f.title} onChange={set("title")} placeholder="Bright 2 BHK near Vijay Nagar square" className={input} /></Field>
        <div className="grid gap-4 sm:grid-cols-4">
          <Field label="BHK">
            <select value={f.bhk} onChange={set("bhk")} className={input}>{[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n} BHK</option>)}</select>
          </Field>
          <Field label="Furnishing">
            <select value={f.furnishing} onChange={set("furnishing")} className={input}>
              <option value="furnished">Furnished</option><option value="semi-furnished">Semi-furnished</option><option value="unfurnished">Unfurnished</option>
            </select>
          </Field>
          <Field label="Area (sq ft)"><input inputMode="numeric" value={f.area_sqft} onChange={set("area_sqft")} placeholder="950" className={input} /></Field>
          <Field label="Available from"><input type="date" value={f.available_from} onChange={set("available_from")} className={input} /></Field>
        </div>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium">Facilities</legend>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {Object.entries(AMENITY_LABEL).map(([k, label]) => (
              <label key={k} className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${amenities.includes(k) ? "border-vault bg-vault-soft" : "border-line"}`}>
                <input type="checkbox" checked={amenities.includes(k)} onChange={() => setAmenities(toggle(amenities, k))} className="accent-vault" />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        <Field label="Description" hint="What's nearby, how the rooms are laid out, water and power, parking, house rules.">
          <textarea rows={4} value={f.description} onChange={set("description")} className={input} />
        </Field>
      </Section>
      <Section n={3} title="Location" hint="Tenants see this on Google Maps.">
        <Field label="Address"><input value={f.address} onChange={set("address")} placeholder="Flat 302, Shanti Residency, Scheme 54" className={input} /></Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Locality"><input value={f.locality} onChange={set("locality")} placeholder="Vijay Nagar" className={input} /></Field>
          <Field label="City">
            <select value={f.city} onChange={set("city")} className={input}>{CITY_OPTIONS.map((c) => <option key={c}>{c}</option>)}</select>
          </Field>
          <Field label="Pin code"><input inputMode="numeric" maxLength={6} value={f.pincode} onChange={set("pincode")} placeholder="452010" className={input} /></Field>
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-sm font-medium">Pin it on the map</span>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button type="button" onClick={locateMe} className="shrink-0 rounded-lg border border-line px-3 py-2.5 text-sm hover:border-vault hover:text-vault">
              Use my current location
            </button>
            <input aria-label="Google Maps link or coordinates" value={mapsText} onChange={(e) => setMapsText(e.target.value)}
              placeholder="or paste a Google Maps link / 22.7533, 75.8937" className={`${input} min-w-0 flex-1`} />
            <button type="button" onClick={readMapsLink} className="shrink-0 rounded-lg bg-ink px-3 py-2.5 text-sm text-white">Set location</button>
          </div>
          {msg && <p className="text-sm text-amber">{msg}</p>}
          {mapSrc ? (
            <>
              <iframe title="Location preview" src={mapSrc} className="h-64 w-full rounded-xl border border-line" loading="lazy" referrerPolicy="no-referrer-when-downgrade" />
              <p className="text-xs text-muted tabular">Pinned at {coords!.lat}, {coords!.lng}. Stand at the building when using your current location.</p>
            </>
          ) : (
            <div className="grid h-40 place-items-center rounded-xl border border-dashed border-line text-sm text-muted">The map preview appears here.</div>
          )}
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={exact} onChange={(e) => setExact(e.target.checked)} className="mt-1 accent-vault" />
            <span>Show the exact location on the listing.<span className="block text-xs text-muted">Off: tenants see the locality only until you confirm a visit. Recommended for privacy.</span></span>
          </label>
        </div>
      </Section>
      <Section n={4} title="Rent and tenancy">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Monthly rent (₹)"><input inputMode="numeric" value={f.rent} onChange={set("rent")} placeholder="18000" className={input} /></Field>
          <Field label="Security deposit (₹)" hint={
            depMonths > 2
              ? <span className="text-amber">{depMonths} months of rent. The Model Tenancy Act caps residential deposits at 2 months, and tenants filter for this.</span>
              : rent ? `${depMonths} month${depMonths === 1 ? "" : "s"} of rent, held in the TrustRent vault, not by you` : "Held in the TrustRent vault during the lease."
          }>
            <input inputMode="numeric" value={f.deposit} onChange={set("deposit")} placeholder={rent ? String(rent * 2) : "36000"} className={input} />
          </Field>
          <Field label="Minimum stay (months)"><input type="number" min={1} max={60} value={f.min_months} onChange={set("min_months")} className={input} /></Field>
          <Field label="Maximum stay (months)"><input type="number" min={1} max={60} value={f.max_months} onChange={set("max_months")} className={input} /></Field>
        </div>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium">Who can rent</legend>
          <div className="flex flex-wrap gap-2">
            {(Object.keys(TENANT_LABEL) as TenantType[]).map((t) => (
              <label key={t} className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm ${tenants.includes(t) ? "border-vault bg-vault-soft" : "border-line"}`}>
                <input type="checkbox" checked={tenants.includes(t)} onChange={() => setTenants(toggle(tenants, t))} className="accent-vault" />
                {TENANT_LABEL[t]}
              </label>
            ))}
          </div>
        </fieldset>
      </Section>
      <Section n={5} title="About you" hint="A few lines so tenants know who they're renting from.">
        <textarea rows={3} value={f.about_owner} onChange={set("about_owner")} placeholder="I'm a retired teacher and live on the ground floor. I respond within a day and prefer working professionals or a small family." className={input} />
      </Section>
      <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-2xl sm:border">
        <p className="text-sm text-muted">
          {rent ? <>{formatINR(rent)}/month, deposit {formatINR(deposit)}</> : "Fill in the details above"}, {photos.length} photo{photos.length === 1 ? "" : "s"}
        </p>
        {error && <p role="alert" className="w-full text-sm text-claim sm:order-first">{error}</p>}
        <button type="submit" disabled={saving} className="rounded-lg bg-vault px-5 py-2.5 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">{saving ? "Publishing..." : "Publish listing"}</button>
      </div>
    </form>
  );
}
