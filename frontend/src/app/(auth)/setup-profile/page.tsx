"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AccountTypeToggle, AuthFrame } from "@/components/auth-ui";
import type { AccountType } from "@/lib/auth";
import { ProfileForm } from "@/components/profile-form";
import { afterSignIn, useAuth } from "@/lib/auth-context";
function SetupProfile() {
  const { user, ready, updateProfile, setAccountType, signOut } = useAuth();
  const [type, setType] = useState<AccountType | null>(null);
  const router = useRouter();
  const next = useSearchParams().get("next");
  useEffect(() => {
    if (ready && !user) router.replace("/login");
  }, [ready, user, router]);
  if (!ready || !user) return null;
  const viaGoogle = user.provider === "google";
  return (
    <AuthFrame
      title="Set up your profile"
      subtitle={`You're signed in with ${viaGoogle ? "Google" : "your account"}. Add the remaining details to continue.`}
    >
      <AccountTypeToggle value={type ?? user.accountType} onChange={setType} />
      <ProfileForm
        withPassword={false}
        requireConsent
        initial={{
          firstName: user.firstName, lastName: user.lastName, username: user.username,
          email: user.email, phone: user.phone ? user.phone.replace(/^(\+\d{1,3})(\d+)$/, "$1 $2") : "+91 ",
          country: user.country || "India",
        }}
        lockEmail={viaGoogle}
        submitLabel="Save and continue"
        busyLabel="Saving..."
        onSubmit={async (values) => {
          let u = await updateProfile(values);
          if (type && type !== u.accountType) u = await setAccountType(type);
          router.replace(afterSignIn(u, next));
        }}
      />
      <button type="button" onClick={() => signOut().then(() => router.replace("/login"))} className="mt-6 w-full text-sm text-muted hover:text-ink">
        Not you? Sign out
      </button>
    </AuthFrame>
  );
}
export default function SetupProfilePage() { // profile setup
  return (
    <Suspense>
      <SetupProfile />
    </Suspense>
  );
}
