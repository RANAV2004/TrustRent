"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
export default function Home() { // home
  const { user, ready } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (ready) router.replace(user ? "/search" : "/login");
  }, [ready, user, router]);
  return <div className="grid min-h-dvh place-items-center text-sm text-muted" role="status">Loading...</div>;
}
