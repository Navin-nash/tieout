# Tieout HTTP API

FastAPI JSON surface consumed by the Next.js dashboard (`tieout serve` → `uvicorn tieout.api.app:app`).
Every response shape matches what the CLI emits with `--json` (SPEC section 12).

## Authentication and tenancy

Better Auth owns sessions in the Next.js app (ADR-002). This API derives the organisation
**server-side from the authenticated session** — never from a request body, path parameter or
client-controlled header.

Until `tieout/platform` merges, the seam is a bearer token encoding the human principal:

```http
Authorization: Bearer controller@acme
```

The org is parsed from the identity (`acme` above). Every data route is scoped to that org.
Cross-org access by id returns `404`.

Policy writes require a human identity; service principals are rejected.

## Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | no | Liveness probe |
| GET | `/close?period=YYYY-MM` | yes | Close status screen |
| POST | `/close?period=YYYY-MM` | yes | Attempt period close (I4 — no override) |
| GET | `/queue` | yes | Review queue (`blocking`, `aging` query flags) |
| POST | `/review/{work_key}` | yes | Approve / reject / reclassify (four-eyes) |
| GET | `/scoreboard` | yes | Seven metrics + baselines + chart |
| POST | `/runs` | yes | Enqueue reconcile run |
| GET | `/runs` | yes | List runs for org |
| GET | `/runs/{run_id}` | yes | Run status and progress |
| PUT | `/runs/{run_id}/uploads/{kind}` | yes | Upload ReconRiver CSV (`internal`, `processor`, `bank`) |
| GET | `/audit/verify` | yes | Hash-chain integrity |
| GET | `/audit/evidence/{work_key}` | yes | Evidence pack for work key |
| PUT | `/policy` | yes | Human policy write with rationale |

### Close status (`GET /close`)

```json
{
  "period": "2026-01",
  "policy_version": "2026.01-r3",
  "state": "CLOSE REFUSED",
  "refused": true,
  "work_items": 1,
  "tiers": {
    "T0": {"count": 0, "dollars": "0"},
    "T1": {"count": 0, "dollars": "0"},
    "T2": {"count": 0, "dollars": "0"},
    "T3": {"count": 1, "dollars": "47900.00"}
  },
  "straight_through_rate": "0",
  "fabrication_rate": "0",
  "blocking": [
    {
      "work_key": "wk_refuse_1",
      "outcome_class": "AMBIGUOUS_MATCH",
      "reason_code": "L2_TWO_CANDIDATES_WITHIN_TOLERANCE",
      "dollars": "47900.00",
      "tier": "T3"
    }
  ],
  "blocking_total": "47900.00"
}
```

`state` is either `CLOSE REFUSED` or `CLOSED`. Straight-through rate and fabrication rate are
always returned together.

`POST /close` returns `409` with `state: CLOSE REFUSED` when blocking items remain. There is
no request body and no `force` parameter.

### Review (`POST /review/{work_key}`)

```json
{
  "action": "approve",
  "identity": "controller@acme",
  "initiator": "manager@acme",
  "note": "reviewed both candidates",
  "reclassify_to": null
}
```

`identity` must match the session. `initiator` is the party that escalated the item; approver
must differ (four-eyes, enforced by `tieout.audit.identity.Approval`).

### Scoreboard (`GET /scoreboard`)

Returns seven metrics, three baselines, two-axis chart points, and per-class precision/recall
when `tieout.score.report` is available. Money and rates are decimal strings, never floats.

### Uploads (`PUT /runs/{run_id}/uploads/{kind}`)

Raw CSV body. Max 50 MiB. Content-Type must be `text/csv`, `application/csv`, or `text/plain`.
Filename is ignored; kind selects the ReconRiver file slot.

## Routes that deliberately do not exist

Mirroring SPEC section 7 — the absence is the feature:

| Absent route | Why |
|--------------|-----|
| `POST /entries` with `{account, amount}` | The plug. Posting goes through matched rows only (`post_matched_entry(match_id)`). |
| `POST /close` with `force` / `override` / `skip_gate` | I4 has no override in code or HTTP. |
| `GET /ground-truth` or holdout CSV paths | Scoring is out-of-process; labels stay outside the reconcile path. |
| `DELETE /audit/events/{id}` | Hash-chained log is append-only. |
| Agent policy mutation | Policy writes require a human session with provenance. |

## Error responses

Safe JSON only — no stack traces, file paths, or secrets:

```json
{"detail": "run not found"}
```

## Running locally

```bash
uv run uvicorn tieout.api.app:app --reload --port 8000
```

## Dependencies not yet merged

| Module | Adapter in `deps.py` |
|--------|---------------------|
| `tieout/platform` | `InMemoryPlatform` — org-scoped runs, queue, audit paths |
| `tieout/close/period.py` | `build_close_report` fallback using gate invariants |
| `tieout/score/report.py` | `build_scoreboard_report` placeholder metrics |

When those modules land, the adapters import them automatically via `importlib.util.find_spec`.
