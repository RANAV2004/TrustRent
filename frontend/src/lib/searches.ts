"use client";
import { api } from "./api";
import type { Filters } from "./listings";
export interface SavedSearch { id: string; name: string; filters: Partial<Filters> & { q: string }; createdAt: string; lastAlertAt: string | null }
export const listSaved = () => api<SavedSearch[]>("/searches");
export const saveSearch = (name: string, filters: Partial<Filters> & { q: string }) => api<SavedSearch>("/searches", { json: { name, filters } });
export const deleteSaved = (id: string) => api<void>(`/searches/${id}`, { method: "DELETE" });
