"use client";
import { usePathname, useRouter } from "next/navigation";
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { clearApiCache } from "./sync";
import { AccountType, authService, isProfileComplete, ProfileInput, SignUpInput, User } from "./auth";
interface AuthContextValue {
  user: User | null;
  ready: boolean;
  requestSignUpCode: (input: SignUpInput) => Promise<{ demoCode?: string }>;
  signUp: (input: SignUpInput) => Promise<User>;
  signIn: (identifier: string, password: string) => Promise<User>;
  signInWithGoogle: (email: string) => Promise<User>;
  requestPasswordReset: (email: string) => Promise<void>;
  updateProfile: (input: ProfileInput) => Promise<User>;
  setAccountType: (type: AccountType) => Promise<User>;
  verifyIdentity: (docType: string, file?: File) => Promise<User>;
  activatePremium: (planId: string, days: number) => Promise<User>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
}
const AuthContext = createContext<AuthContextValue | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let alive = true;
    authService.current().then((u) => {
      if (!alive) return;
      setUser(u);
      setReady(true);
    });
    return () => {
      alive = false;
    };
  }, []);
  const keep = useCallback(async (p: Promise<User>) => {
    const u = await p;
    setUser(u);
    return u;
  }, []);
  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      ready,
      requestSignUpCode: (i) => authService.requestSignUpCode(i),
      signUp: (i) => keep(authService.signUp(i)),
      signIn: (id, pw) => keep(authService.signIn(id, pw)),
      signInWithGoogle: (email) => keep(authService.signInWithGoogle(email)),
      requestPasswordReset: (e) => authService.requestPasswordReset(e),
      updateProfile: (i) => keep(authService.updateProfile(i)),
      setAccountType: (t) => keep(authService.setAccountType(t)),
      verifyIdentity: (d, f) => keep(authService.verifyIdentity(d, f)),
      activatePremium: (p, days) => keep(authService.activatePremium(p, days)),
      refreshUser: async () => {
        const u = await authService.current();
        if (u) setUser(u);
        return u;
      },
      signOut: async () => {
        await authService.signOut();
        clearApiCache();
        setUser(null);
      },
    }),
    [user, ready, keep],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>.");
  return ctx;
}
export function afterSignIn(u: User, next: string | null): string {
  if (!isProfileComplete(u)) return `/setup-profile${next ? `?next=${encodeURIComponent(next)}` : ""}`;
  return next && next.startsWith("/") && !next.startsWith("//") ? next : homeFor(u);
}
export function homeFor(u: User): string {
  if (u.isAdmin) return "/admin";
  return u.accountType === "owner" ? "/owner" : "/search";
}
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const needsLogin = ready && !user;
  const needsProfile = ready && !!user && !isProfileComplete(user);
  useEffect(() => {
    if (needsLogin) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    else if (needsProfile) router.replace(`/setup-profile?next=${encodeURIComponent(pathname)}`);
  }, [needsLogin, needsProfile, pathname, router]);
  if (!ready || needsLogin || needsProfile) {
    return (
      <div className="grid min-h-dvh place-items-center text-sm text-muted" role="status">
        Loading...
      </div>
    );
  }
  return <>{children}</>;
}
