import { auth } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";

// Better Auth catch-all route handler — mounts every auth endpoint under
// /api/auth/* (sign-in, sign-up, session, ...). See web/README.md.
export const { POST, GET } = toNextJsHandler(auth);