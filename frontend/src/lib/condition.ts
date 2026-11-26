"use client";
import { api, API_URL, ApiError, getToken } from "./api";
export type Stage = "move_in" | "move_out";
export interface ConditionPhoto {
  id: string;
  side: "tenant" | "owner";
  stage: Stage;
  room: string;
  note: string | null;
  uploadedBy: string;
  uploadedAt: string;
  fileHash: string;
  receipt: string | null;
  verified: boolean;
}
export interface ConditionSet {
  rooms: string[];
  side: "tenant" | "owner" | null;
  compare: boolean;
  canUpload: Record<Stage, boolean>;
  photos: ConditionPhoto[];
}
export const STAGE_LABEL: Record<Stage, string> = { move_in: "Move-in", move_out: "Move-out" };
export const getPhotos = (depositId: string) => api<ConditionSet>(`/deposits/${depositId}/photos`);
export function uploadPhoto(depositId: string, stage: Stage, room: string, note: string, file: File) { // photo upload
  const form = new FormData();
  form.set("stage", stage);
  form.set("room", room);
  form.set("note", note);
  form.set("file", file);
  return api<ConditionPhoto>(`/deposits/${depositId}/photos`, { form });
}
export async function photoBlobUrl(depositId: string, photoId: string): Promise<string> { // photo file
  const token = getToken();
  const res = await fetch(`${API_URL}/deposits/${depositId}/photos/${photoId}/file`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status === 410 ? "This photo is no longer stored." : "Couldn't load the photo.", res.status);
  return URL.createObjectURL(await res.blob());
}