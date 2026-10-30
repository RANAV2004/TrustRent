"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import { AccountTypeToggle, AuthFrame, FormError, SecondaryLink, SubmitButton, TextField } from "@/components/auth-ui";
import { ProfileForm } from "@/components/profile-form";
import { AccountType, AuthError, SignUpInput } from "@/lib/auth";
import { afterSignIn, useAuth } from "@/lib/auth-context";
const RESEND_SECONDS = 60;
function SignUp() {
  const { user, ready, requestSignUpCode, signUp } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [type, setType] = useState<AccountType>(() => (params.get("as") === "owner" ? "owner" : "seeker"));
  const creating = useRef(false);
  const [pending, setPending] = useState<SignUpInput | null>(null);
  const [demoCode, setDemoCode] = useState<string | undefined>();
  const [code, setCode] = useState("");
  const [wait, setWait] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (ready && user && !creating.current) router.replace(afterSignIn(user, null));
  }, [ready, user, router]);
  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);
  const [sentTo, setSentTo] = useState<string | null>(null);
  async function sendCode(input: SignUpInput, resend = false) {
    const to = input.email.trim().toLowerCase();
    if (!resend && to === sentTo && wait > 0) {
      setPending(input);
      setNotice("Use the code we already sent to this email.");
      return;
    }
    const r = await requestSignUpCode(input);
    setDemoCode(r.demoCode);
    setPending(input);
    setSentTo(to);
    setCode("");
    setWait(RESEND_SECONDS);
  }
  async function run(action: () => Promise<void>) {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await action();
    } catch (err) {
      setError(err instanceof AuthError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }
  function verify(e: FormEvent) {
    e.preventDefault();
    if (!pending) return;
    if (code.length !== 6) {
      setError("Enter the 6-digit code from the email.");
      return;
    }
    run(async () => {
      creating.current = true;
      try {
        const u = await signUp({ ...pending, emailCode: code });
        router.replace(afterSignIn(u, null));
      } catch (err) {
        creating.current = false;
        throw err;
      }
    });
  }
  return (
    <AuthFrame
      title={pending ? "Verify your email" : "Create your account"}
      subtitle={pending
        ? `We sent a 6-digit code to ${pending.email}. Enter it to finish creating your account.`
        : type === "owner"
          ? "List your home in minutes. We verify your identity and property papers before it goes live."
          : "Search verified homes, message owners and book visits."}
    >
      <div className={pending ? "hidden" : undefined}>
        <AccountTypeToggle value={type} onChange={setType} />
        <ProfileForm
          withPassword
          requireConsent
          submitLabel="Continue"
          busyLabel="Sending code..."
          onSubmit={async (values) => {
            setNotice(null);
            setError(null);
            await sendCode({ ...values, password: values.password ?? "", accountType: type });
          }}
        />
      </div>
      {pending && (
        <form onSubmit={verify} className="flex flex-col gap-4" noValidate>
          {demoCode ? (
            <p className="rounded-lg border border-line bg-surface px-3 py-2.5 text-sm">
              Demo mode: no email is sent. Use code <strong className="tabular">{demoCode}</strong>.
            </p>
          ) : (
            <p className="text-sm text-muted">It can take a minute to arrive, so check your spam folder too. The code expires in 10 minutes.</p>
          )}
          <TextField
            id="emailCode"
            label="Verification code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          />
          {notice && <p className="text-sm text-vault">{notice}</p>}
          <FormError message={error} />
          <SubmitButton busy={busy}>{busy ? "Creating account..." : "Verify and create account"}</SubmitButton>
          <div className="flex justify-between text-sm">
            <button type="button" onClick={() => { setPending(null); setError(null); }} className="text-vault hover:underline">
              Change details
            </button>
            <button
              type="button"
              disabled={wait > 0 || busy}
              onClick={() => run(async () => { await sendCode(pending, true); setNotice("We've sent a new code."); })}
              className="text-vault hover:underline disabled:text-muted disabled:no-underline"
            >
              {wait > 0 ? `Resend code in ${wait}s` : "Resend code"}
            </button>
          </div>
        </form>
      )}
      <p className="mt-8 text-center text-sm text-muted">
        Already have an account? <SecondaryLink href={`/login?as=${type}`}>Sign in</SecondaryLink>
      </p>
    </AuthFrame>
  );
}
export default function SignUpPage() { // sign up
  return (
    <Suspense>
      <SignUp />
    </Suspense>
  );
}
