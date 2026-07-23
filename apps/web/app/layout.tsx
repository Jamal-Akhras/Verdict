import type { Metadata } from "next";
import Link from "next/link";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import { AuthControls } from "@/components/AuthControls";
import { DemoBadge } from "@/components/DemoBadge";

export const metadata: Metadata = {
  title: "Verdict",
  description:
    "Transparent AI software studio. Founder-governed, approval-based - no black boxes.",
};

// Clerk is optional: without a publishable key the app runs in open
// demo mode (the API resolves everyone to the demo user).
const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="bg-white border-b border-stone-200 px-6 py-3 flex items-center gap-6">
          <Link href="/" className="font-semibold tracking-tight text-lg">
            Verdict
          </Link>
          <nav className="flex gap-4 text-sm text-stone-500">
            <Link href="/" className="hover:text-stone-900">Dashboard</Link>
            <Link href="/intake" className="hover:text-stone-900">New idea</Link>
            <Link href="/projects/demo" className="hover:text-stone-900">Example project</Link>
          </nav>
          <span className="ml-auto flex items-center gap-3">
            <DemoBadge />
            <span className="text-xs text-stone-500">
              You hold final say · every action auditable
            </span>
            {clerkEnabled && <AuthControls />}
          </span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  if (!clerkEnabled) return <Shell>{children}</Shell>;
  return (
    <ClerkProvider>
      <Shell>{children}</Shell>
    </ClerkProvider>
  );
}
