"use client";

import { createAuthClient } from "better-auth/react";

// Same-origin client for Better Auth. baseURL is omitted because dev (:3000)
// and prod serve the API from the same origin as the UI.
export const authClient = createAuthClient();

// Convenience exports used by UI screens (Wave 3 consumers).
export const { useSession, signIn, signUp, signOut } = authClient;