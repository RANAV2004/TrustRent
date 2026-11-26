"use client";
import { FormEvent, useState } from "react";
import { AuthFrame, FormError, SecondaryLink, SubmitButton, TextField } from "@/components/auth-ui";
import { ApiError, apiMode } from "@/lib/api";
import { applicationStatus, ApplicationStatus, applyAsLawyer, PRACTICE_AREAS } from "@/lib/legal";

const ID_DOCS = ["Masked Aadhaar card", "PAN card", "Passport", "Voter ID", "Driving licence"];

function FileField({ id, label, hint, accept, file, onPick, error }: {
  id: string; label: string; hint: string; accept: string; file: File | null; onPick: (f: File | null) => void; error?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5 text-sm">
      <label htmlFor={id} className="font-medium">{label}</label>
      <input id={id} type="file" accept={accept} onChange={(e) => onPick(e.target.files?.[0] ?? null)}
        aria-invalid={error ? true : undefined}
        className="rounded-lg border border-line bg-surface px-3 py-2 file:mr-3 file:rounded-md file:border-0 file:bg-vault-soft file:px-2 file:py-1 file:text-vault" />
      <span className={`text-xs ${error ? "text-claim" : "text-muted"}`}>{error ?? (file ? `Selected: ${file.name}` : hint)}</span>
    </div>
  );
}

function StatusCheck() {
  const [reference, setReference] = useState("");
  const [email, setEmail] = useState("");
  const [result, setResult] = useState<ApplicationStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function check(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setBusy(true);
    try {
      setResult(await applicationStatus(reference.trim(), email.trim()));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't check right now. Try again.");
    } finally {
      setBusy(false);
    }
  }
  const label = { pending: "Waiting for review (usually 24 to 48 hours)", approved: "Approved: your sign-in details were sent to your email", rejected: "Not approved" };
  return (
    <form onSubmit={check} className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4">
      <p className="text-sm font-medium">Already applied? Check your status</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField id="ref" label="Reference" placeholder="LAW-1A2B3C4D" value={reference} onChange={(e) => setReference(e.target.value)} />
        <TextField id="status-email" label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </div>
      <button type="submit" disabled={busy || !reference.trim() || !email.trim()}
        className="w-fit rounded-lg border border-line px-4 py-2 text-sm hover:border-ink/40 disabled:opacity-50">
        {busy ? "Checking..." : "Check status"}
      </button>
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
      {result && (
        <p role="status" className="text-sm">
          <strong>{label[result.status]}</strong>
          {result.reviewNote && <span className="block text-muted">Reason: {result.reviewNote}</span>}
        </p>
      )}
    </form>
  );
}

export default function LawyerApplyPage() {
  const [v, setV] = useState({
    fullName: "", email: "", phone: "+91 ", city: "", barCouncil: "", enrolmentNo: "", experienceYears: "",
    languages: "", officeAddress: "", about: "", idDocType: "",
  });
  const [areas, setAreas] = useState<string[]>([]);
  const [photo, setPhoto] = useState<File | null>(null);
  const [idProof, setIdProof] = useState<File | null>(null);
  const [certificate, setCertificate] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ reference: string; email: string } | null>(null);
  const set = (k: keyof typeof v) => (value: string) => setV((s) => ({ ...s, [k]: value }));

  function validate() {
    const e: Record<string, string> = {};
    if (v.fullName.trim().split(/\s+/).length < 2) e.fullName = "Enter your first name and surname.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.email.trim())) e.email = "Enter a valid email address.";
    if (v.phone.replace(/\D/g, "").length < 10) e.phone = "Enter your phone number with country code.";
    if (v.city.trim().length < 2) e.city = "Enter the city you practise in.";
    if (v.barCouncil.trim().length < 3) e.barCouncil = "Enter your State Bar Council.";
    if (!/^[A-Za-z0-9][A-Za-z0-9/.\- ]{3,39}$/.test(v.enrolmentNo.trim())) e.enrolmentNo = "Enter your enrolment number, e.g. MP/1234/2015.";
    const years = Number(v.experienceYears);
    if (v.experienceYears === "" || !Number.isInteger(years) || years < 0 || years > 60) e.experienceYears = "Enter whole years (0 to 60).";
    if (!areas.length) e.practiceAreas = "Choose at least one practice area.";
    if (v.officeAddress.trim().length < 10) e.officeAddress = "Enter your full office address.";
    if (!v.idDocType) e.idDocType = "Choose the ID you're uploading.";
    if (!photo) e.photo = "Add a clear photo of your face.";
    if (!idProof) e.idProof = "Upload your ID.";
    if (!certificate) e.enrolmentCertificate = "Upload your enrolment certificate or Bar Council ID card.";
    return e;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length) return setError("Check the highlighted fields.");
    if (!consent) return setError("Tick the declaration to continue.");
    const form = new FormData();
    Object.entries(v).forEach(([k, val]) => form.append(k, val.trim()));
    areas.forEach((a) => form.append("practiceAreas", a));
    form.append("photo", photo!);
    form.append("idProof", idProof!);
    form.append("enrolmentCertificate", certificate!);
    setBusy(true);
    try {
      const r = await applyAsLawyer(form);
      setDone({ reference: r.reference, email: r.email });
      window.scrollTo({ top: 0 });
    } catch (err) {
      if (err instanceof ApiError && err.field) setErrors({ [err.field]: err.message });
      setError(err instanceof ApiError ? err.message : "Couldn't send your application. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!apiMode) {
    return (
      <AuthFrame title="Apply as a lawyer" subtitle="Lawyer accounts need the TrustRent server.">
        <p className="text-sm text-muted">This demo isn&apos;t connected to the server, so lawyer applications are switched off.</p>
        <p className="mt-6 text-sm"><SecondaryLink href="/lawyer-login">Back to lawyer sign in</SecondaryLink></p>
      </AuthFrame>
    );
  }

  if (done) {
    return (
      <AuthFrame title="Application received" subtitle="Thank you. We'll check your details and documents.">
        <div className="flex flex-col gap-4 text-sm">
          <p role="status" className="rounded-lg border border-vault/30 bg-vault-soft px-3 py-3 text-vault">
            Your reference is <strong>{done.reference}</strong>. Verification usually takes <strong>24 to 48 hours</strong>.
          </p>
          <p>Once you&apos;re approved, we&apos;ll email your <strong>username and temporary password</strong> to {done.email}. Use them on the lawyer sign-in page, then choose your own password.</p>
          <p className="text-muted">Keep your reference to check the status of your application.</p>
          <StatusCheck />
          <p><SecondaryLink href="/lawyer-login">Back to lawyer sign in</SecondaryLink></p>
        </div>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame title="Apply as a lawyer" subtitle="Get verified to receive rental agreement requests from home owners on TrustRent.">
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <TextField id="fullName" label="Full name (as on your enrolment)" autoComplete="name" value={v.fullName} onChange={(e) => set("fullName")(e.target.value)} error={errors.fullName} />
        <TextField id="email" label="Email" type="email" autoComplete="email" value={v.email} onChange={(e) => set("email")(e.target.value)} error={errors.email}
          hint="We'll send your sign-in details here. It can't already be used by a TrustRent account." />
        <TextField id="phone" label="Phone" type="tel" autoComplete="tel" value={v.phone} onChange={(e) => set("phone")(e.target.value)} error={errors.phone} />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField id="city" label="City you practise in" value={v.city} onChange={(e) => set("city")(e.target.value)} error={errors.city} />
          <TextField id="experienceYears" label="Years of practice" inputMode="numeric" value={v.experienceYears} onChange={(e) => set("experienceYears")(e.target.value)} error={errors.experienceYears} />
        </div>
        <TextField id="barCouncil" label="State Bar Council" placeholder="Bar Council of Madhya Pradesh" value={v.barCouncil} onChange={(e) => set("barCouncil")(e.target.value)} error={errors.barCouncil} />
        <TextField id="enrolmentNo" label="Enrolment number" placeholder="MP/1234/2015" value={v.enrolmentNo} onChange={(e) => set("enrolmentNo")(e.target.value)} error={errors.enrolmentNo} />
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1.5 text-sm font-medium">Practice areas</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {PRACTICE_AREAS.map((a) => (
              <label key={a} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={areas.includes(a)}
                  onChange={(e) => setAreas((s) => (e.target.checked ? [...s, a] : s.filter((x) => x !== a)))} />
                {a}
              </label>
            ))}
          </div>
          {errors.practiceAreas && <span className="text-xs text-claim">{errors.practiceAreas}</span>}
        </fieldset>
        <TextField id="languages" label="Languages (optional)" placeholder="Hindi, English, Marathi" value={v.languages} onChange={(e) => set("languages")(e.target.value)} error={errors.languages} />
        <TextField id="officeAddress" label="Office address" autoComplete="street-address" value={v.officeAddress} onChange={(e) => set("officeAddress")(e.target.value)} error={errors.officeAddress} />
        <div className="flex flex-col gap-1.5">
          <label htmlFor="about" className="text-sm font-medium">About your practice (optional)</label>
          <textarea id="about" rows={3} maxLength={1000} value={v.about} onChange={(e) => set("about")(e.target.value)}
            className="w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-[15px] focus:border-vault focus:outline-none" />
          <span className="text-xs text-muted">Facts only, such as the work you do. Bar Council rules don&apos;t allow advertising or fee offers.</span>
        </div>
        <FileField id="photo" label="Your photo" hint="A clear photo of your face. Owners will see it." accept="image/jpeg,image/png,image/webp"
          file={photo} onPick={setPhoto} error={errors.photo} />
        <div className="flex flex-col gap-1.5">
          <label htmlFor="idDocType" className="text-sm font-medium">ID document</label>
          <select id="idDocType" value={v.idDocType} onChange={(e) => set("idDocType")(e.target.value)}
            className="rounded-lg border border-line bg-surface px-3 py-2.5 text-[15px]">
            <option value="">Choose...</option>
            {ID_DOCS.map((d) => <option key={d}>{d}</option>)}
          </select>
          {errors.idDocType && <span className="text-xs text-claim">{errors.idDocType}</span>}
        </div>
        <FileField id="idProof" label="Upload your ID" hint="Photo or PDF, up to 10 MB. Mask the first 8 Aadhaar digits." accept="image/*,application/pdf"
          file={idProof} onPick={setIdProof} error={errors.idProof} />
        <FileField id="enrolmentCertificate" label="Enrolment certificate or Bar Council ID card" hint="Photo or PDF, up to 10 MB." accept="image/*,application/pdf"
          file={certificate} onPick={setCertificate} error={errors.enrolmentCertificate} />
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1" />
          <span>I&apos;m an advocate enrolled with the Bar Council named above, the details are true, and I agree to TrustRent checking them.</span>
        </label>
        <FormError message={error} />
        <SubmitButton busy={busy}>{busy ? "Sending..." : "Send for verification"}</SubmitButton>
      </form>
      <div className="mt-8 flex flex-col gap-6">
        <StatusCheck />
        <p className="text-center text-sm text-muted">Already have your sign-in details? <SecondaryLink href="/lawyer-login">Sign in as a lawyer</SecondaryLink></p>
      </div>
    </AuthFrame>
  );
}
