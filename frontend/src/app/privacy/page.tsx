import type { Metadata } from "next";
import { Contact, GRIEVANCE_OFFICER, LegalPage } from "@/components/legal-page";
export const metadata: Metadata = { title: "TrustRent Privacy Policy" };
export default function PrivacyPage() { // privacy
  return (
    <LegalPage title="Privacy Policy">
      <p>TrustRent helps people in India find verified rental homes and keeps security deposits on a tamper-proof record. This policy explains what personal data we collect, why, who we share it with, and the rights you have under the Digital Personal Data Protection Act, 2023 (DPDP Act).</p>
      <h2>What we collect</h2>
      <ul>
        <li><strong>Account details:</strong> name, username, email, phone number, country, and a scrambled (hashed) password. If you sign in with Google, we receive your name and email from Google.</li>
        <li><strong>Verification documents:</strong> the ID you upload (we ask for a masked Aadhaar, PAN, passport, voter ID or driving licence) and, for owners, a property document and the property address.</li>
        <li><strong>Listings:</strong> photos, address, location pin, rent, deposit and other details owners publish.</li>
        <li><strong>Messages and visit requests</strong> between tenants and owners.</li>
        <li><strong>Payments:</strong> amount, date and the payment reference from our payment gateway. We never see or store your card, UPI PIN or bank login.</li>
        <li><strong>Deposit records:</strong> deposit amount, deductions, refunds and their reasons.</li>
      </ul>
      <h2>Why we use it</h2>
      <ul>
        <li>To create and secure your account, including emailing a code to verify your email address when you sign up.</li>
        <li>To verify identities and property ownership before homes are listed or deposits are paid.</li>
        <li>To show listings, deliver messages and arrange visits.</li>
        <li>To take payments, hold deposits, settle and refund them, and keep receipts.</li>
        <li>To prevent fraud and meet legal obligations.</li>
      </ul>
      <p>By creating an account you consent to this processing. You can withdraw consent at any time by deleting your account (see below); this does not affect processing already done, or records we must keep by law.</p>
      <h2>How we protect it</h2>
      <ul>
        <li>ID and property documents are encrypted (AES-256-GCM) before they are stored, and only authorised TrustRent reviewers can open them.</li>
        <li>A street address is shown only after the owner confirms a visit, unless the owner chooses to show it.</li>
        <li>Deposit receipts recorded on the blockchain or in our ledger contain only a deposit ID, amounts and a cryptographic fingerprint. They never contain your name, phone, address or documents.</li>
      </ul>
      <h2>Who we share it with</h2>
      <ul>
        <li>The other party of a rental: owners see a tenant&apos;s name and messages; tenants see the owner&apos;s name and, after a confirmed visit, the address.</li>
        <li>TrustRent admins, who can read conversations on the platform only to check safety reports and settle deposit disputes.</li>
        <li>Service providers who process data for us: payment gateway (Razorpay), email provider (Google Gmail) for verification codes, cloud hosting and storage. They may use it only to provide their service.</li>
        <li>Authorities, when the law requires it.</li>
      </ul>
      <p>We do not sell your personal data.</p>
      <h2>How long we keep it</h2>
      <p>We keep account data while your account is open. Verification documents are kept only as long as needed to verify you and resolve disputes. Payment and deposit records are kept for the period required by Indian tax and accounting law. Blockchain receipts cannot be deleted, which is why they hold no personal data.</p>
      <h2>Your rights</h2>
      <p>You can ask to access, correct or erase your personal data, nominate someone to exercise your rights, and raise a grievance. Write to <Contact />. We reply within 30 days.</p>
      {GRIEVANCE_OFFICER && <p><strong>Grievance Officer:</strong> {GRIEVANCE_OFFICER}, <Contact /></p>}
      <p>If you are not satisfied with our response, you may complain to the Data Protection Board of India.</p>
      <h2>Children</h2>
      <p>TrustRent is for adults. We do not knowingly create accounts for anyone under 18.</p>
      <h2>Changes</h2>
      <p>We will post changes here and, for significant ones, tell you by email or in the app.</p>
    </LegalPage>
  );
}
