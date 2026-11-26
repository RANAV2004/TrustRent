"use client";
import { api, API_URL, ApiError, getToken } from "./api";

export interface LawyerCard {
  id: string; name: string; photo: string | null; city: string; barCouncil: string; enrolmentNo: string;
  experienceYears: number; practiceAreas: string[]; languages: string[]; phone: string; email: string;
  officeAddress: string; about: string;
}
export interface CaseSummary {
  id: string; subject: string; side: "owner" | "lawyer" | "admin";
  owner: { id: string; name: string; phone: string; email: string };
  lawyer: { id: string; name: string; available: boolean };
  listing: { id: string; title: string; area: string } | null;
  createdAt: string; updatedAt: string; lastMessage: string; unread: number; agreements: number;
}
export interface CaseMessage { id: string; senderId: string; senderName: string; from: "owner" | "lawyer"; text: string; createdAt: string }
export interface AgreementDoc {
  id: string; caseId: string; title: string; fileName: string; fileHash: string; size: number; createdAt: string;
  uploadedBy: string; sharedWith?: { id: string; name: string; sharedAt: string }[];
}
export interface CaseDetail extends CaseSummary { messages: CaseMessage[]; documents: AgreementDoc[] }
export interface SharedAgreement extends AgreementDoc { sharedAt: string; owner: string; lawyer: string; listing: string | null }
export interface Contact { id: string; name: string; username: string; via: string }
export interface ApplicationReceipt { reference: string; email: string; status: string }
export interface ApplicationStatus { reference: string; status: "pending" | "approved" | "rejected"; submittedAt: string; reviewedAt: string | null; reviewNote: string | null }

export const PRACTICE_AREAS = [
  "Rental and lease agreements", "Property and real estate", "Tenancy disputes", "Property registration",
  "Civil law", "Consumer law", "Documentation and drafting",
];

export const getLawyerOptions = () => api<{ practiceAreas: string[]; idDocTypes: string[] }>("/lawyers/options");
export const applyAsLawyer = (form: FormData) => api<ApplicationReceipt>("/lawyers/applications", { form });
export const applicationStatus = (reference: string, email: string) =>
  api<ApplicationStatus>(`/lawyers/applications/status?${new URLSearchParams({ reference, email })}`);
export const getLawyers = () => api<LawyerCard[]>("/lawyers");
export const getContacts = () => api<Contact[]>("/legal/contacts");
export const getCases = () => api<CaseSummary[]>("/legal/cases");
export const getCase = (id: string) => api<CaseDetail>(`/legal/cases/${id}`);
export const openCase = (lawyerId: string, listingId: string | null, message: string) =>
  api<CaseDetail>("/legal/cases", { json: { lawyerId, listingId, message } });
export const sendCaseMessage = (id: string, text: string) => api<CaseDetail>(`/legal/cases/${id}/messages`, { json: { text } });
export const markCaseRead = (id: string) => api(`/legal/cases/${id}/read`, { method: "POST" });
export function uploadAgreement(caseId: string, title: string, file: File) {
  const form = new FormData();
  form.append("title", title);
  form.append("file", file);
  return api<CaseDetail>(`/legal/cases/${caseId}/agreements`, { form });
}
export const shareAgreement = (id: string, tenantId: string) => api<CaseDetail>(`/legal/agreements/${id}/share`, { json: { tenantId } });
export const sharedWithMe = () => api<SharedAgreement[]>("/legal/agreements");

export async function downloadAgreement(doc: { id: string; fileName: string }) {
  const res = await fetch(`${API_URL}/legal/agreements/${doc.id}/file`, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) throw new ApiError("Couldn't download the document. Try again.", res.status);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = doc.fileName;
  a.rel = "noopener";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export const fileSize = (bytes: number) =>
  bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
