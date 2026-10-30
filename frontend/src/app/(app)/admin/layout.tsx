"use client";
import { apiMode } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!apiMode || !user?.isAdmin) {
    return <p className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">The admin console is only for TrustRent admins{apiMode ? "" : " and needs the backend"}.</p>;
  }
  return <>{children}</>;
}
