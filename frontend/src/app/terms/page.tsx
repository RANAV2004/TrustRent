import type { Metadata } from "next";
import { Contact, LegalPage } from "@/components/legal-page";
export const metadata: Metadata = { title: "TrustRent Terms of Use" };
export default function TermsPage() { // terms
  return (
    <LegalPage title="Terms of Use">
      <p>These terms apply when you use TrustRent to find a home, list a home, or pay and settle a security deposit. By creating an account you agree to them.</p>
      <h2>Accounts</h2>
      <ul>
        <li>You must be 18 or older and give true, current details.</li>
        <li>Keep your password and one-time codes private. You are responsible for activity on your account.</li>
        <li>Choose &ldquo;looking for a home&rdquo; or &ldquo;renting out my home&rdquo; when you sign up. You can switch later.</li>
      </ul>
      <h2>Verification</h2>
      <ul>
        <li>Owners must upload a valid ID and a document proving they own, co-own or are authorised to rent the property. Listings go live only after TrustRent approves them.</li>
        <li>Tenants must verify their ID before buying Premium or paying a deposit.</li>
        <li>Uploading forged or someone else&apos;s documents is prohibited and will be reported where the law requires.</li>
      </ul>
      <h2>Listings and visits</h2>
      <ul>
        <li>Owners are responsible for the accuracy of their listings, photos, rent and deposit terms.</li>
        <li>TrustRent does not inspect homes. Visit a home before paying a deposit; the app unlocks deposit payment only after the owner confirms your visit.</li>
        <li>Be respectful in messages. Harassment, discrimination or spam leads to removal.</li>
      </ul>
      <h2>Security deposits</h2>
      <ul>
        <li>The deposit is paid to TrustRent through our payment gateway, not to the owner, and a receipt is recorded on a tamper-proof ledger.</li>
        <li>At move-out the owner proposes any deduction with a reason. The tenant accepts it or disputes it. In a dispute, TrustRent reviews the evidence and its decision on the split is final on the platform; it does not stop either party from going to court.</li>
        <li>The tenant&apos;s refund goes back to the original payment method. The owner&apos;s share is paid out to the owner once settled.</li>
        <li>Deductions may never exceed the deposit. We recommend deposits of no more than two months&apos; rent, in line with the Model Tenancy Act, 2021.</li>
      </ul>
      <h2>Premium</h2>
      <p>Premium gives early access to contact owners of new listings for 48 hours and a Verified Premium badge. It is a one-time purchase for the chosen period, does not renew automatically, and is not refundable once the period has started, except where the law requires.</p>
      <h2>Fees and payments</h2>
      <p>Prices are shown before you pay and include applicable taxes unless stated. Payments are processed by Razorpay under its terms.</p>
      <h2>Our role and liability</h2>
      <p>TrustRent connects tenants and owners and holds deposits under these terms. We are not a party to the rental agreement between you. To the extent the law allows, we are not liable for indirect losses, and our total liability for any claim is limited to the fees you paid us in the 12 months before it, except for deposit amounts we hold for you.</p>
      <h2>Ending your account</h2>
      <p>You can close your account at any time by writing to <Contact />, once any deposit you are part of is settled. We may suspend accounts that break these terms.</p>
      <h2>Law and disputes</h2>
      <p>These terms are governed by the laws of India. Courts in Indore, Madhya Pradesh have jurisdiction, subject to any consumer-protection rights you have.</p>
      <h2>Contact</h2>
      <p>Questions or complaints: <Contact />.</p>
    </LegalPage>
  );
}
