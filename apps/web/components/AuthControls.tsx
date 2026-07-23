"use client";
import { SignInButton, SignedIn, SignedOut, UserButton } from "@clerk/nextjs";

// Rendered only when Clerk is configured (the layout checks the publishable
// key before mounting ClerkProvider + this component).
export function AuthControls() {
  return (
    <span className="flex items-center gap-3">
      <SignedOut>
        <SignInButton mode="modal">
          <button className="rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-700">
            Sign in
          </button>
        </SignInButton>
      </SignedOut>
      <SignedIn>
        <UserButton afterSignOutUrl="/" />
      </SignedIn>
    </span>
  );
}
