import data from "@/data/listings.json";
import { apiMode } from "./api";
import { readStore } from "./local-store";
import { KEYS } from "./sync";
export type Furnishing = "furnished" | "semi-furnished" | "unfurnished";
export type TenantType = "family" | "bachelor_male" | "bachelor_female" | "student" | "any";
export interface LandlordRecord {
  name: string;
  verified: boolean;
  tenancies_completed: number;
  full_refunds: number;
  disputes_lost: number;
}
export interface Listing {
  id: string;
  title: string;
  city: string;
  locality: string;
  pincode: string;
  lat: number;
  lng: number;
  rent: number;
  deposit: number;
  bhk: number;
  furnishing: Furnishing;
  area_sqft: number;
  amenities: string[];
  preferred_tenants: TenantType[];
  available_from: string;
  landlord: LandlordRecord;
  min_months: number;
  max_months: number;
  listed_at?: string;
  listed_days_ago?: number;
  owner_id?: string;
  owner_name?: string;
  address?: string;
  show_exact_location?: boolean;
  description?: string;
  about_owner?: string;
  photos?: string[];
  status?: "live" | "paused" | "blocked";
  admin_note?: string | null;
}
export const EARLY_ACCESS_HOURS = 48;
const SAMPLE = data as Listing[];
function sampleListings(now = Date.now()): Listing[] {
  return SAMPLE.map((l) => ({
    ...l,
    show_exact_location: false,
    listed_at: new Date(now - (l.listed_days_ago ?? 30) * 86_400_000 - (l.listed_days_ago === 0 ? 6 * 3_600_000 : 0)).toISOString(),
  }));
}
export function allListings(): Listing[] {
  if (apiMode) return readStore<Listing[]>(KEYS.listings, []);
  let own: Listing[] = [];
  if (typeof window !== "undefined") {
    try {
      own = (JSON.parse(localStorage.getItem("trustrent-owner-listings") || "[]") as Listing[]).filter((l) => l.status !== "paused");
    } catch {
      own = [];
    }
  }
  return [...own, ...sampleListings()];
}
export const AMENITY_LABEL: Record<string, string> = {
  parking: "Parking", lift: "Lift", power_backup: "Power backup", wifi: "Wi-Fi", ac: "AC", gym: "Gym",
  security: "Security", water_24x7: "24x7 water", balcony: "Balcony", pets_allowed: "Pets allowed",
  washing_machine: "Washing machine", near_metro: "Near metro",
};
export const TENANT_LABEL: Record<TenantType, string> = {
  family: "Family", bachelor_male: "Bachelor (male)", bachelor_female: "Bachelor (female)", student: "Students", any: "Anyone",
};
const CITY_ALIASES: Record<string, string> = { bangalore: "Bengaluru", bengaluru: "Bengaluru", blr: "Bengaluru", indore: "Indore", pune: "Pune" };
export interface QueryMatch {
  kind: "pincode" | "city" | "locality" | "none";
  label: string;
  results: Listing[];
}
const LOCALITY_ALIASES: Record<string, string> = {
  vijayanagar: "vijay nagar", vijaynagar: "vijay nagar", vijaynagr: "vijay nagar", scheme54: "vijay nagar",
  piplyahana: "pipliyahana", pipliahana: "pipliyahana", pipliyana: "pipliyahana", pipliana: "pipliyahana",
  piplihana: "pipliyahana", pipaliyahana: "pipliyahana", piplyana: "pipliyahana",
};
export function searchListings(raw: string, all: Listing[] = allListings()): QueryMatch {
  const typed = raw.trim().toLowerCase().replace(/\s+/g, " ");
  const q = LOCALITY_ALIASES[typed.replace(/\s/g, "")] ?? typed;
  if (!q) return { kind: "none", label: "", results: [] };
  const byRef = all.find((l) => l.id.toLowerCase() === q);
  if (byRef) return { kind: "locality", label: `listing ${byRef.id}`, results: [byRef] };
  if (/^\d{6}$/.test(q)) {
    const results = all.filter((l) => l.pincode === q);
    const areas = Array.from(new Set(results.map((l) => l.locality)));
    return { kind: "pincode", label: `pin code ${q}${areas.length ? ` (${areas.join(", ")})` : ""}`, results };
  }
  if (/^\d{3,5}$/.test(q)) {
    const results = all.filter((l) => l.pincode.startsWith(q));
    return { kind: "pincode", label: `pin codes starting ${q}`, results };
  }
  const cities = Array.from(new Set(all.map((l) => l.city)));
  const city = CITY_ALIASES[q] ?? cities.find((c) => c.toLowerCase() === q);
  if (city) return { kind: "city", label: city, results: all.filter((l) => l.city === city) };
  const locs = Array.from(new Map(all.map((l) => [l.locality, { locality: l.locality, city: l.city }])).values());
  const loc = locs.find((l) => l.locality.toLowerCase() === q) ??
    locs.find((l) => l.locality.toLowerCase().replace(/\s/g, "") === q.replace(/\s/g, "")) ??
    locs.find((l) => l.locality.toLowerCase().includes(q));
  if (loc) return { kind: "locality", label: `${loc.locality}, ${loc.city}`, results: all.filter((l) => l.locality === loc.locality) };
  return { kind: "none", label: raw.trim(), results: [] };
}
export function getListing(id: string): Listing | undefined {
  if (apiMode) {
    return allListings().find((l) => l.id === id) ?? readStore<Listing[]>(KEYS.myListings, []).find((l) => l.id === id);
  }
  return allListings().find((l) => l.id === id) ??
    (typeof window !== "undefined"
      ? (JSON.parse(localStorage.getItem("trustrent-owner-listings") || "[]") as Listing[]).find((l) => l.id === id)
      : undefined);
}
export function earlyAccessHoursLeft(l: Listing, now = Date.now()): number {
  if (!l.listed_at) return 0;
  const left = EARLY_ACCESS_HOURS - (now - new Date(l.listed_at).getTime()) / 3_600_000;
  return left > 0 ? Math.ceil(left) : 0;
}
export function mapEmbedUrl(l: Listing, exact = !!l.show_exact_location): string {
  const q = exact ? `${l.lat},${l.lng}` : `${l.locality}, ${l.city} ${l.pincode}`;
  return `https://maps.google.com/maps?q=${encodeURIComponent(q)}&z=${exact ? 16 : 14}&output=embed`;
}
export function mapsLink(l: Listing, exact = !!l.show_exact_location): string {
  const q = exact ? `${l.lat},${l.lng}` : `${l.locality}, ${l.city} ${l.pincode}`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`;
}
export interface Filters {
  budgetMin: number | null;
  budgetMax: number | null;
  bhk: number[];
  furnishing: Furnishing[];
  amenities: string[];
  tenantType: TenantType | "";
  depositWithinCap: boolean;
  withHistory: boolean;
  availableBy: string;
}
export const EMPTY_FILTERS: Filters = {
  budgetMin: null, budgetMax: null, bhk: [], furnishing: [], amenities: [], tenantType: "",
  depositWithinCap: false, withHistory: false, availableBy: "",
};
export function activeFilterCount(f: Filters): number {
  return [
    f.budgetMin !== null || f.budgetMax !== null, f.bhk.length > 0, f.furnishing.length > 0, f.amenities.length > 0,
    !!f.tenantType, f.depositWithinCap, f.withHistory, !!f.availableBy,
  ].filter(Boolean).length;
}
export function applyFilters(list: Listing[], f: Filters): Listing[] {
  return list.filter((l) => {
    if (f.budgetMin !== null && l.rent < f.budgetMin) return false;
    if (f.budgetMax !== null && l.rent > f.budgetMax) return false;
    if (f.bhk.length && !f.bhk.some((b) => (b >= 3 ? l.bhk >= 3 : l.bhk === b))) return false;
    if (f.furnishing.length && !f.furnishing.includes(l.furnishing)) return false;
    if (f.amenities.some((a) => !l.amenities.includes(a))) return false;
    if (f.tenantType && !l.preferred_tenants.includes("any") && !l.preferred_tenants.includes(f.tenantType)) return false;
    if (f.depositWithinCap && depositMonths(l) > 2) return false;
    if (f.withHistory && l.landlord.tenancies_completed === 0) return false;
    if (f.availableBy && l.available_from > f.availableBy) return false;
    return true;
  });
}
export type SortKey = "recommended" | "rent-asc" | "rent-desc" | "available" | "trust";
export const SORT_LABEL: Record<SortKey, string> = {
  recommended: "Recommended", "rent-asc": "Rent: low to high", "rent-desc": "Rent: high to low",
  available: "Available soonest", trust: "Best landlord record",
};
export function sortListings(list: Listing[], key: SortKey): Listing[] {
  const copy = [...list];
  switch (key) {
    case "rent-asc": return copy.sort((a, b) => a.rent - b.rent);
    case "rent-desc": return copy.sort((a, b) => b.rent - a.rent);
    case "available": return copy.sort((a, b) => a.available_from.localeCompare(b.available_from));
    case "trust": return copy.sort((a, b) => trustScore(b) - trustScore(a));
    default:
      return copy.sort((a, b) => trustScore(b) + (depositMonths(b) <= 2 ? 0.3 : 0) - (trustScore(a) + (depositMonths(a) <= 2 ? 0.3 : 0)) || a.rent - b.rent);
  }
}
export function depositMonths(l: Listing): number {
  return Math.round((l.deposit / l.rent) * 10) / 10;
}
export function trustScore(l: Listing): number {
  const r = l.landlord;
  if (!r.tenancies_completed) return 0.5;
  const raw = r.full_refunds / r.tenancies_completed - 0.5 * (r.disputes_lost / r.tenancies_completed);
  return Math.min(1, Math.max(0, 0.5 + (raw - 0.5) * Math.min(1, r.tenancies_completed / 3)));
}
export function trustLine(l: Listing): { text: string; tone: "good" | "neutral" | "warn" } {
  const r = l.landlord;
  if (!r.tenancies_completed) return { text: "New landlord on TrustRent", tone: "neutral" };
  const text = `Returned full deposit in ${r.full_refunds} of ${r.tenancies_completed} tenancies`;
  if (r.disputes_lost > 0 || r.full_refunds / r.tenancies_completed < 0.75) return { text, tone: "warn" };
  return { text, tone: "good" };
}
const TONES = ["#C9D8D2", "#E2D6C2", "#D3D6E4", "#CFE0E6", "#D9D4E2", "#D5DDD0", "#E4D9C6"];
export function photoTone(l: Listing): string {
  let h = 0;
  for (const c of l.id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return TONES[h % TONES.length];
}
