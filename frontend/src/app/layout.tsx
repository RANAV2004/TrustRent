import type { Metadata } from "next";
import "./globals.css";
import { ErrorReporter } from "@/components/error-reporter";
import { AuthProvider } from "@/lib/auth-context";
export const metadata: Metadata = {
  title: "TrustRent",
  description:
    "Verified homes and tamper-proof security deposit receipts for renters and owners in India.",
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-IN">
      <body>
        <ErrorReporter />
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
