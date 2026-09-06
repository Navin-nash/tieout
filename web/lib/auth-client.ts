"use client";

import { createAuthClient } from "better-auth/react";
import { organizationClient } from "better-auth/client/plugins";

// Same-origin client for Better Auth. baseURL is omitted because dev (:3000)
// and prod serve the API from the same origin as the UI.
export const authClient = createAuthClient({
  plugins: [organizationClient()],
});

// Convenience exports used by UI screens.
export const { useSession, signIn, signUp, signOut } = authClient;
