"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { signIn, signUp } from "@/lib/auth-client";

type Mode = "sign-in" | "sign-up";

const MIN_PASSWORD_LENGTH = 12; // must match emailAndPassword.minPasswordLength in lib/auth.ts

/**
 * DESIGN.md section 8 "Input": errors carry a text label *and* a border colour
 * change, never colour alone. The border uses the refuse text colour as section
 * 12.2 permits, but the error is styled as an inline field message rather than
 * a red alert banner - the REFUSE stamp's meaning must not be diluted into
 * generic form validation.
 */
const FIELD =
  "h-11 w-full rounded-md border bg-paper px-3 font-ui text-body text-ink outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-paper";

export function SignInForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") ?? "/close";

  const [mode, setMode] = useState<Mode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (mode === "sign-up" && password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }

    setPending(true);
    const result =
      mode === "sign-in"
        ? await signIn.email({ email, password })
        : await signUp.email({ email, password, name: name || email });
    setPending(false);

    if (result.error) {
      // Surface the server's message rather than a generic one: a rate-limit
      // rejection and a wrong password are different problems for the user.
      setError(result.error.message ?? "Sign-in failed. Check the email and password.");
      return;
    }

    router.push(next);
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} className="mt-8 flex max-w-md flex-col gap-4">
      {mode === "sign-up" ? (
        <label className="flex flex-col gap-1.5">
          <span className="font-ui text-caption font-medium uppercase tracking-caption text-ink-muted">
            Name
          </span>
          <input
            className={`${FIELD} border-border-interactive`}
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
          />
        </label>
      ) : null}

      <label className="flex flex-col gap-1.5">
        <span className="font-ui text-caption font-medium uppercase tracking-caption text-ink-muted">
          Email
        </span>
        <input
          type="email"
          required
          className={`${FIELD} ${error ? "border-refuse" : "border-border-interactive"}`}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
      </label>

      <label className="flex flex-col gap-1.5">
        <span className="font-ui text-caption font-medium uppercase tracking-caption text-ink-muted">
          Password
        </span>
        <input
          type="password"
          required
          minLength={mode === "sign-up" ? MIN_PASSWORD_LENGTH : undefined}
          className={`${FIELD} ${error ? "border-refuse" : "border-border-interactive"}`}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === "sign-in" ? "current-password" : "new-password"}
        />
        {mode === "sign-up" ? (
          <span className="font-ui text-body-sm text-ink-muted">
            At least {MIN_PASSWORD_LENGTH} characters.
          </span>
        ) : null}
      </label>

      {error ? (
        <p role="alert" className="font-ui text-body-sm text-refuse">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={pending}
        className="h-11 rounded-md bg-ink px-4 font-ui text-body font-medium text-paper transition-opacity duration-fast ease-standard hover:opacity-90 focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-paper disabled:opacity-50"
      >
        {pending ? "Working…" : mode === "sign-in" ? "Sign in" : "Create account"}
      </button>

      <button
        type="button"
        onClick={() => {
          setMode(mode === "sign-in" ? "sign-up" : "sign-in");
          setError(null);
        }}
        className="self-start font-ui text-body-sm text-ink-muted underline underline-offset-4 hover:text-ink"
      >
        {mode === "sign-in" ? "Create an account" : "I already have an account"}
      </button>
    </form>
  );
}
