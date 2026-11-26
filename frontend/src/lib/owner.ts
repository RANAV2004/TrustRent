"use client";
import type { User } from "./auth";
import type { Furnishing, Listing, TenantType } from "./listings";
import { api, apiMode, dataUrlToBlob } from "./api";
import { readStore, uid, writeStore } from "./local-store";
import { KEYS, refreshListings, refreshOwner } from "./sync";
export type ApplicationStatus = "not_started" | "submitted" | "approved" | "rejected";
export interface OwnerApplication {
  userId: string;
  status: ApplicationStatus;
  relation: "owner" | "co-owner" | "authorised";
  idDocType: string;
  idFileName: string;
  propertyDocType: string;
  propertyFileName: string;
  propertyAddress: string;
  submittedAt?: string;
  reviewedAt?: string;
  reviewNote?: string;
}
const APPS_KEY = "trustrent-owner-applications";
const LISTINGS_KEY = "trustrent-owner-listings";
export const ID_DOCS = ["Masked Aadhaar card", "PAN card", "Passport", "Voter ID", "Driving licence"];
export const PROPERTY_DOCS = ["Sale deed / title deed", "Latest property tax receipt", "Electricity bill in owner's name", "Society share certificate", "Registered rent authorisation"];
export function getApplication(userId: string): OwnerApplication | null {
  if (apiMode) return readStore<OwnerApplication | null>(KEYS.application, null);
  return readStore<OwnerApplication[]>(APPS_KEY, []).find((a) => a.userId === userId) ?? null;
}
function saveApplication(app: OwnerApplication) {
  const all = readStore<OwnerApplication[]>(APPS_KEY, []).filter((a) => a.userId !== app.userId);
  writeStore(APPS_KEY, [...all, app]);
}
export async function submitApplication(
  app: Omit<OwnerApplication, "status" | "submittedAt">,
  files: { id: File; property: File },
) {
  if (apiMode) {
    const form = new FormData();
    form.append("relation", app.relation);
    form.append("idDocType", app.idDocType);
    form.append("propertyDocType", app.propertyDocType);
    form.append("propertyAddress", app.propertyAddress);
    form.append("idFile", files.id);
    form.append("propertyFile", files.property);
    await api("/owner/application", { form });
    await refreshOwner();
    return;
  }
  saveApplication({ ...app, status: "submitted", submittedAt: new Date().toISOString() });
}
export async function simulateReview(userId: string, approve: boolean) {
  if (apiMode) {
    await api(`/owner/application/${userId}/review`, { json: { approve } });
    await refreshOwner();
    return;
  }
  const app = getApplication(userId);
  if (!app) return;
  saveApplication({
    ...app,
    status: approve ? "approved" : "rejected",
    reviewedAt: new Date().toISOString(),
    reviewNote: approve ? undefined : "The property document was unclear. Upload a sharper photo of every page.",
  });
}
export interface OwnerListingInput {
  title: string;
  address: string;
  locality: string;
  city: string;
  pincode: string;
  lat: number;
  lng: number;
  show_exact_location: boolean;
  rent: number;
  deposit: number;
  bhk: number;
  furnishing: Furnishing;
  area_sqft: number;
  amenities: string[];
  preferred_tenants: TenantType[];
  available_from: string;
  min_months: number;
  max_months: number;
  description: string;
  about_owner: string;
  photos: string[];
}
export function allOwnerListings(): Listing[] {
  return readStore<Listing[]>(LISTINGS_KEY, []);
}
export function ownerListingsFor(userId: string): Listing[] {
  if (apiMode) return readStore<Listing[]>(KEYS.myListings, []);
  return allOwnerListings().filter((l) => l.owner_id === userId);
}
export async function createOwnerListing(owner: User, input: OwnerListingInput): Promise<Listing> {
  if (apiMode) {
    const { photos, ...data } = input;
    const form = new FormData();
    form.append("data", JSON.stringify(data));
    photos.forEach((p, i) => form.append("photos", dataUrlToBlob(p), `photo-${i + 1}.jpg`));
    const created = await api<Listing>("/owner/listings", { form });
    await Promise.all([refreshOwner(), refreshListings()]);
    return created;
  }
  const listing: Listing = {
    ...input,
    id: uid("TR").toUpperCase(),
    owner_id: owner.id,
    owner_name: `${owner.firstName} ${owner.lastName}`,
    status: "live",
    listed_at: new Date().toISOString(),
    landlord: { name: `${owner.firstName} ${owner.lastName}`, verified: true, tenancies_completed: 0, full_refunds: 0, disputes_lost: 0 },
  };
  writeStore(LISTINGS_KEY, [listing, ...allOwnerListings()]);
  return listing;
}
export async function setListingStatus(id: string, status: "live" | "paused") {
  if (apiMode) {
    await api(`/owner/listings/${id}`, { method: "PATCH", json: { status } });
    await Promise.all([refreshOwner(), refreshListings()]);
    return;
  }
  writeStore(LISTINGS_KEY, allOwnerListings().map((l) => (l.id === id ? { ...l, status } : l)));
}
export async function deleteOwnerListing(id: string) {
  if (apiMode) {
    await api(`/owner/listings/${id}`, { method: "DELETE" });
    await Promise.all([refreshOwner(), refreshListings()]);
    return;
  }
  writeStore(LISTINGS_KEY, allOwnerListings().filter((l) => l.id !== id));
}
export function compressImage(file: File, max = 1200, quality = 0.72): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith("image/")) return reject(new Error(`${file.name} is not an image.`));
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, max / Math.max(img.width, img.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/jpeg", quality));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error(`Could not read ${file.name}.`));
    };
    img.src = url;
  });
}
export function parseMapsLink(text: string): { lat: number; lng: number } | null {
  const m = text.match(/@(-?\d{1,2}\.\d+),\s*(-?\d{1,3}\.\d+)/) ??
    text.match(/[?&](?:q|query|ll)=(-?\d{1,2}\.\d+),\s*(-?\d{1,3}\.\d+)/) ??
    text.match(/^\s*(-?\d{1,2}\.\d+),\s*(-?\d{1,3}\.\d+)\s*$/) ??
    text.match(/!3d(-?\d{1,2}\.\d+)!4d(-?\d{1,3}\.\d+)/);
  if (!m) return null;
  const lat = Number(m[1]);
  const lng = Number(m[2]);
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
  return { lat, lng };
}
