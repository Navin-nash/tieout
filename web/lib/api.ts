// Typed client over the SPEC section 12 JSON contract.
//
// Two modes, selected by `NEXT_PUBLIC_TIEOUT_API_MODE`:
//
//   fixture  (default)  Serves the labelled ReconRiver sample data in
//                       lib/fixtures.ts. This exists so the landing-page,
//                       dashboard-ui and agent-ui workers can build screens
//                       before the FastAPI layer lands.
//   live                Fetches from `NEXT_PUBLIC_TIEOUT_API_URL`.
//
// Every response is wrapped in `ApiResult`, which carries `source` and, in
// fixture mode, `notice`. SPEC section 12 requires example data to be plainly
// labelled as ReconRiver and never presented as a real company's books, so a
// caller cannot render fixture data without having been handed the label.
//
// Identity: SPEC section 8 requires a named human reviewer, and four-eyes is
// enforced server-side in Python. This client's only job is to carry the
// authenticated identity through on review actions - it does not decide
// anything about permissions and must not grow a role model.

import {
  FIXTURE_CLOSE_STATUS,
  FIXTURE_NOTICE,
  FIXTURE_REVIEW_QUEUE,
  FIXTURE_SCOREBOARD,
} from "@/lib/fixtures";
import type {
  CloseStatus,
  ReviewQueue,
  ReviewRequest,
  ReviewResult,
  Scoreboard,
} from "@/lib/api-types";

export * from "@/lib/api-types";
export { FIXTURE_NOTICE } from "@/lib/fixtures";

export type ApiMode = "fixture" | "live";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_TIEOUT_API_URL ?? "http://localhost:8000";

/**
 * Fixture is the default until the `api-layer` worker lands. Set
 * `NEXT_PUBLIC_TIEOUT_API_MODE=live` to talk to FastAPI.
 */
export const API_MODE: ApiMode =
  process.env.NEXT_PUBLIC_TIEOUT_API_MODE === "live" ? "live" : "fixture";

export type ApiResult<T> = {
  data: T;
  source: ApiMode;
  /** Present in fixture mode only. Render it. */
  notice?: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly path: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function fixture<T>(data: T): ApiResult<T> {
  return { data, source: "fixture", notice: FIXTURE_NOTICE };
}

async function request<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(
      `${init?.method ?? "GET"} ${path} failed with ${response.status}`,
      response.status,
      path,
    );
  }

  return { data: (await response.json()) as T, source: "live" };
}

/** Screen 1 - close status and disposition breakdown (SPEC section 12). */
export async function getCloseStatus(period: string): Promise<ApiResult<CloseStatus>> {
  if (API_MODE === "fixture") return fixture(FIXTURE_CLOSE_STATUS);
  return request<CloseStatus>(`/close/${encodeURIComponent(period)}`);
}

/** Screen 2 - review queue, sorted by materiality x age. */
export async function getReviewQueue(
  period: string,
  options: { blocking?: boolean } = {},
): Promise<ApiResult<ReviewQueue>> {
  if (API_MODE === "fixture") {
    if (!options.blocking) return fixture(FIXTURE_REVIEW_QUEUE);
    return fixture({
      ...FIXTURE_REVIEW_QUEUE,
      items: FIXTURE_REVIEW_QUEUE.items.filter((item) => item.blocksClose),
    });
  }
  const query = options.blocking ? "?blocking=true" : "";
  return request<ReviewQueue>(`/queue/${encodeURIComponent(period)}${query}`);
}

/** Screen 3 - scoreboard: seven metrics, three baselines, per-class table. */
export async function getScoreboard(period: string): Promise<ApiResult<Scoreboard>> {
  if (API_MODE === "fixture") return fixture(FIXTURE_SCOREBOARD);
  return request<Scoreboard>(`/score/${encodeURIComponent(period)}`);
}

/**
 * Approve / reject / reclassify. `actor` is the authenticated human, read from
 * the Better Auth session by the caller - never from user input, and never
 * defaulted. Four-eyes is enforced by the server; a rejection here is expected
 * and must be surfaced, not swallowed.
 *
 * Fixture mode deliberately throws rather than pretending a decision was
 * recorded: a fake success on a disposition-affecting action is exactly the
 * credibility failure this product exists to argue against.
 */
export async function submitReview(review: ReviewRequest): Promise<ApiResult<ReviewResult>> {
  if (API_MODE === "fixture") {
    throw new ApiError(
      "Review actions are disabled in fixture mode - no decision was recorded. Set NEXT_PUBLIC_TIEOUT_API_MODE=live.",
      501,
      "/review",
    );
  }
  return request<ReviewResult>("/review", {
    method: "POST",
    body: JSON.stringify(review),
  });
}
