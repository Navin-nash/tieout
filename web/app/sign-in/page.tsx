import { Suspense } from "react";
import type { Metadata } from "next";

import { SignInForm } from "./sign-in-form";

export const metadata: Metadata = { title: "Sign in" };

/**
 * The one auth surface the shell owns. Its whole job is to establish who the
 * logged-in human is (SPEC section 8) so that identity can be written onto
 * review decisions. There is no role selection here and no permissions model -
 * see lib/auth.ts for why.
 */
export default function SignInPage() {
  return (
    <div className="mx-auto flex w-full max-w-[45rem] flex-1 flex-col justify-center px-6 py-16">
      <p className="font-ui text-caption font-medium uppercase tracking-caption text-ink-muted">
        Tieout
      </p>
      <h1 className="mt-2 font-statement text-display-lg tracking-display-lg text-ink">
        Sign in
      </h1>
      <p className="mt-3 max-w-md font-ui text-body text-ink-muted">
        Your identity is recorded on every review decision you make. Four-eyes
        separation is enforced by the engine, not by this form.
      </p>
      {/* useSearchParams() reads ?next=, which forces a client bailout; the
          boundary keeps the rest of the page statically rendered. */}
      <Suspense fallback={null}>
        <SignInForm />
      </Suspense>
    </div>
  );
}
