# Platform Layer — Postgres, tenancy, jobs, storage

> Implements ADR-003 (*Tieout as a multi-tenant SaaS*). Billing is explicitly out of scope and
> nothing here touches payments, plans, checkout or metering.

The platform layer is what turns Tieout from a terminal tool into an application: a relational
read model, a tenant boundary that is enforced structurally, a background job queue, and
per-organisation file storage. It wraps the engine; it does not weaken it.

| Module | Responsibility |
|---|---|
| `tieout/platform/settings.py` | Environment configuration. `DATABASE_URL` required, no default. |
| `tieout/platform/models.py` | The relational model. All money `NUMERIC`. |
| `tieout/platform/session.py` | Engine, session factory, the deliberately awkward unscoped path. |
| `tieout/platform/tenancy.py` | `OrgScope` and `tenant_session` — the security boundary. |
| `tieout/platform/jobs.py` | Enqueue, `SKIP LOCKED` claim, progress, user-safe failure. |
| `tieout/platform/worker.py` | Runnable worker: `python -m tieout.platform.worker`. |
| `tieout/platform/storage.py` | Per-org paths; traversal, symlink and holdout guards. |
| `tieout/platform/testing.py` | Skip marker and per-test org fixtures for the three test files. |
| `migrations/` | Alembic, async, URL from the environment only. |

---

## 1. Dependencies this layer needs in `pyproject.toml`

**These are not yet in `pyproject.toml`.** That file is owned by another worker, so this one
reports the requirement instead of editing it. Add to `[project].dependencies`:

```toml
"sqlalchemy[asyncio]>=2.0.36",
"alembic>=1.14",
"psycopg[binary]>=3.2",
"pydantic-settings>=2.6",
```

`sqlalchemy[asyncio]` pulls in `greenlet`, which the async bridge requires. `psycopg[binary]`
ships a recent libpq; the pure-Python `psycopg` needs a system libpq at least version 13 for
`channel_binding`, which hosted providers ask for.

No test-only dependency is needed. The three test modules are plain synchronous pytest
functions that drive their async bodies through `asyncio.run`, precisely so that `pytest-asyncio`
— which would need an `asyncio_mode` key in the same contended `pyproject.toml` — is not
required.

Until the dependencies land, the three platform test modules `pytest.importorskip` themselves
and the suite stays green rather than failing collection.

---

## 2. The auth boundary — what Better Auth owns, what this owns

Authentication is **not** part of this layer and this service never sees a credential.

| Better Auth owns (Next.js app, ADR-002) | This layer owns |
|---|---|
| Users, passwords, sessions, cookies | Nothing about identity |
| Organisation records and membership (organization plugin) | A **mirror**: `organisation`, `membership` |
| Deciding *who* is signed in and which org is active | Consuming the already-decided org id |
| Role and permission checks | Row-level tenant filtering by that org id |

`organisation.id` and `membership.user_id` are `VARCHAR(64)` holding **Better Auth's own
identifiers**, not UUIDs minted here. The mirror exists so the queue can show "reviewed by whom"
and screens can sort by member without a round trip to the Next.js app. It is a read-side copy:
nothing in this package treats a `membership` row as an authorisation decision.

The contract at the seam is one value. The API layer must take the active organisation id from
a **server-verified session** and pass it to `OrgScope`. Everything downstream is then safe by
construction. If that one value can be chosen by the client, no filter below helps — the filter
will faithfully scope to whichever org the caller named.

---

## 3. Tenancy is a security boundary, not a convention

ADR-003: *"No query may omit the org scope. Enforce it structurally."*

### How

Every tenant table inherits one mixin:

```python
class Run(Base, OrgScoped): ...
```

`OrgScoped` supplies the `org_id` column **and** marks the class. Both together, so a table
cannot be tenant data without the column, and cannot have the column without being filtered.

`tenant_session(scope)` registers two SQLAlchemy events on the session it hands back:

1. **`do_orm_execute`** attaches `with_loader_criteria(OrgScoped, lambda cls: cls.org_id == org_id)`
   to every ORM `SELECT`, `UPDATE` and `DELETE`. SQLAlchemy applies that criterion to the primary
   entity, to joined entities, to relationship lazy-loads, and to ORM-enabled update and delete.
2. **`before_flush`** stamps `org_id` on new rows from the session's scope and refuses the flush
   if an object arrives carrying a different one — so a row cannot be inserted into, or moved
   into, another tenant.

### Why structurally rather than by convention

A `WHERE org_id = :org` added by habit is right until the day somebody writes a query in a hurry,
and there is no way to test "every future query". Attaching the criterion to the *session* means
the filter travels with any statement handed to that session, including statements written
elsewhere, in another module, next month.

The specific case this defends is not the forgotten `WHERE` on a list query. It is the caller who
already knows another org's row id:

```python
# org A's session, org B's disposition id
await session.execute(update(Disposition).where(Disposition.id == b_id).values(...))
# rowcount == 0
```

`tests/test_tenancy.py` asserts exactly this for **runs, work items, verdicts, queue items,
prior decisions, uploads, policy versions, entities and jobs** — reads by primary key, by
`Session.get`, by `count`, through a join, and writes via update and delete. Each case also
asserts the row *is* visible to its own org, so no assertion is vacuous.

### The unscoped path

It exists, because the worker must claim a job before it can know whose job it is. It is
`tieout.platform.session.unscoped_session(reason)`, it is not exported from
`tieout.platform.__init__`, and `reason` is checked against a four-value allowlist
(`worker-claim`, `provisioning`, `migration`, `test`) rather than logged. Reaching for it is a
deliberate, greppable act; getting it by accident is not possible.

---

## 4. The relational model

Per ADR-003, Postgres is the **derived read model plus everything genuinely relational**.

```
organisation ──┬─ membership                     (Better Auth mirror)
               ├─ entity                          (reporting entity; consolidation out of scope)
               ├─ policy_version                  (versioned document + provenance)
               ├─ upload                          (one row per file)
               ├─ prior_decision                  (SPEC §9 decision memory)
               ├─ job                             (queue)
               └─ run ──┬─ work_item ── verdict ── disposition
                        └─ job
```

### What is deliberately *not* here

**The hash-chained event log.** ADR-003 is explicit: it stays on disk as built
(`tieout/audit/events.py`). Its canonicalisation rules and literal-digest regression test are
the audit guarantee, and re-implementing them against a relational store for no gain would put
the one tested invariant at risk. `run.event_log_path` points at the log;
`run.event_log_head_hash` is the external anchor `EventLog.verify(expected_head_hash=...)` needs,
because without one a truncated log is a valid prefix of itself. A test asserts no `event` table
exists.

### Money

**Every money column is `NUMERIC(18, 2)`. There is no `DOUBLE PRECISION`, `REAL` or `FLOAT`
column anywhere in this schema**, and `tests/test_platform_models.py` walks `Base.metadata` and
fails if one ever appears. The blanket ban is easier to keep than a per-column judgement about
what counts as money.

| Table | Column |
|---|---|
| `work_item` | `amount` |
| `verdict` | `amount_delta`, `fee_explained_delta` |
| `disposition` | `amount` |
| `prior_decision` | `amount_delta` |

`verdict.confidence` is `NUMERIC(5, 4)` for the same reason. It is compared against the
0.95 / 0.90 / 0.60 tier boundaries in SPEC section 6, and `0.95` has no exact binary float
representation. Every amount carries a `currency` column beside it, mirroring the currency
tagging in `tieout/ingest/money.py`.

`Base.type_annotation_map` has **no entry for `float`**, so annotating a column `Mapped[float]`
fails at class definition rather than quietly creating a double precision column.

### Invariants restated at the database

The engine enforces I1–I4; the schema declines to contradict them.

| Constraint | What it holds |
|---|---|
| `DispositionAction` enum | Four values. No `FORCE`, no `OVERRIDE`, no `PLUG` — not even as a string. |
| `ck_disposition_refuse_is_blocking` | A `REFUSE` row cannot declare itself non-blocking (I4). |
| `ck_disposition_four_eyes` | `reviewed_by <> approved_by`, mirroring `tieout/audit/identity.py`. |
| `ck_prior_decision_human_only` | `decided_by LIKE 'human:%'` — the memory replays only a human's judgment (SPEC §9). |
| `ck_policy_version_set_by_is_human` | Policy is read-only to the agent (ADR-003). |
| `prior_decision` has no `tier`/`action` column | A prior decision is evidence to cite, never permission to post. |

Enums render as `VARCHAR` plus a `CHECK`, not native Postgres enum types: same guarantee at the
database, and adding a value later is one `ALTER` rather than the native-enum dance Alembic
cannot autogenerate.

### What the three screens read

| Screen (SPEC §12) | Query |
|---|---|
| 1 · Close status | `disposition` grouped by `tier`/`action` with `SUM(amount)`; blocking list ordered by `amount DESC` (`ix_disposition_org_queue`, `ix_work_item_org_amount`) |
| 2 · Review queue | `disposition WHERE review_state = 'open'` ordered by materiality × age; `verdict` for reason code and feature deltas; `prior_decision` for the citation |
| 3 · Scoreboard | `verdict` grouped by `outcome_class` (`ix_verdict_org_outcome`), against the `policy_version` in force at the time |

---

## 5. Background jobs

Postgres-backed. **No Redis, no Celery** — an extra service to deploy for one low-throughput
queue. The claim is one statement:

```sql
SELECT ... FROM job
 WHERE status = 'queued' AND available_at <= now()
 ORDER BY available_at, created_at
 LIMIT 1
   FOR UPDATE SKIP LOCKED
```

`FOR UPDATE` locks the row for the transaction; `SKIP LOCKED` makes a second worker step over it
rather than block. The status flip to `running` is what keeps the job unavailable after the lock
releases at commit.

```
queued ──claim──> running ──┬── complete ──> completed
                            └── fail ──┬── attempts < max ──> queued (available_at += backoff)
                                       └── attempts = max ──> failed  (terminal)
```

- **Attempts and backoff.** 10s, 60s, 5min. A job at `max_attempts` stays `failed` and the claim
  query — which only looks at `status = 'queued'` — never sees it again. It does not spin.
- **Progress.** `0…100`, clamped, mirrored onto `run.progress` so the UI polls one thing.
- **Error messages are safe to show a user.** `safe_error_message` passes through an exception's
  explicit `user_message` (still redacted) and reduces anything else to a generic sentence plus
  the exception class name. Windows paths, POSIX paths, URLs with credentials and long hex
  blobs are stripped. No traceback ever reaches the column; `log.exception` keeps the detail
  server-side.
- **Two transactions per iteration.** Claim commits immediately; the handler then runs in a
  *tenant* session scoped to the claimed job's org. Holding the claim transaction open for a
  whole reconcile would keep a row lock for minutes and turn a crashed worker into a stuck queue.

### The ceiling, stated honestly

```python
# ponytail: single polling worker, SKIP LOCKED claim. Fine to ~1 run/sec.
# Run N workers if throughput matters -- the claim is already safe.
```

There is no scheduler, no priority, no dead-letter queue and no cron. Add them when there is a
second job kind that needs one.

### Registering work

This module knows nothing about reconciliation. Whoever owns the work registers a handler:

```python
from tieout.platform import jobs

async def reconcile(ctx: jobs.JobContext) -> None:
    await ctx.progress(10)
    ...

jobs.register_handler("reconcile", reconcile)
```

---

## 6. Storage layout

```
<DATA_ROOT>/
├── raw/                     # ReconRiver inputs; the agent's allowed-read set
├── holdout/                 # expected_reconciliation.csv -- NEVER reachable from below
└── orgs/
    └── <org_id>/
        ├── uploads/<upload-uuid>.csv
        └── runs/<run-uuid>/events.jsonl      # the hash-chained log for that run
```

Org roots are **siblings** of the holdout directory, never ancestors.

- **The client's filename is never used as a path.** `safe_stored_name` returns the upload's own
  UUID plus a whitelisted extension. A filename of `../../holdout/expected_reconciliation.csv`
  becomes `<uuid>.csv` in the org's uploads directory.
- **Containment is checked on the real path.** `resolve_within_org` compares
  `os.path.realpath(candidate)` against `os.path.realpath(org_root)`. A string-prefix check
  passes happily for a symlink whose lexical path stays inside the root; the realpath check does
  not. Both the symlinked-file and symlinked-parent-directory cases are tested, and on Windows
  the parent case runs against a directory junction so it is not skipped on a developer box.
- **Org ids are validated before becoming directory names** — `[A-Za-z0-9_-]{1,64}`, no reserved
  Windows device names.
- **Ground-truth isolation.** Any path resolving into `holdout/`, and any path named
  `expected_reconciliation.csv`, raises `ForbiddenPathError` regardless of how it got there.
  `assert_reconcile_inputs_are_not_ground_truth` catches the same mistake one step earlier, where
  a run's input set is assembled.

`tieout/ingest/paths.py` is **reused, not reimplemented**: it guards the read side (what ingest
may open) and raises `ForbiddenPathError`; this module guards the write side and raises the same
type, so a caller catches one exception for "the path guard said no". A test asserts the two
allowlists agree.

---

## 7. Running it

### Configuration

`DATABASE_URL` is required and there is deliberately no default — a default pointing at a dev
database is how production rows end up in the wrong place. A plain provider URL works as-is;
`postgresql://` and `postgres://` are rewritten onto `postgresql+psycopg://`, and a wrong driver
(`psycopg2`, `asyncpg`) fails at startup rather than at first query.

```bash
DATABASE_URL=postgresql://user:password@host:5432/tieout   # required
DATA_ROOT=data                                             # default: data
MAX_UPLOAD_BYTES=67108864                                  # default: 64 MiB
SQL_ECHO=false
TIEOUT_DB_HOSTADDR=                                        # see "DNS" below
```

`.env` at the repo root is read automatically and is gitignored. Never commit it.

### Local Postgres

`docker-compose.yml` in the repo root runs Postgres 17 on port **5433** (5433, not 5432, so it
does not collide with a system Postgres):

```bash
docker compose up -d
export DATABASE_URL=postgresql://tieout:tieout@localhost:5433/tieout
```

A hosted Postgres works identically — set `DATABASE_URL` and skip compose. The schema in this
repo was migrated and tested against both shapes; see "Verification" below.

### Migrations

```bash
alembic upgrade head        # apply
alembic current             # what is applied
alembic downgrade -1        # roll back one
alembic revision --autogenerate -m "..."   # after changing models.py
```

`alembic.ini` carries **no `sqlalchemy.url`**. `migrations/env.py` reads `DATABASE_URL` through
`tieout.platform.settings`, so a migration cannot run against a different database than the app.
`compare_type` and `compare_server_default` are on, so a `NUMERIC` someone quietly widened — or
worse, turned into a float — shows up in an autogenerated diff.

Initial revision: `c5333aa811a5` (`platform schema`), 11 tables.

### The worker

```bash
python -m tieout.platform.worker                     # poll every second
python -m tieout.platform.worker --poll-seconds 0.5 --log-level DEBUG
```

Run more than one if throughput ever matters; the claim is already safe.

### Tests

```bash
pytest tests/test_platform_models.py        # no database needed, never skips
DATABASE_URL=... pytest tests/test_tenancy.py tests/test_jobs.py
```

The database tests skip with a clear reason when `DATABASE_URL` is unset or the schema has not
been migrated. They deliberately do not fall back to SQLite: `NUMERIC` semantics,
`FOR UPDATE SKIP LOCKED` and `with_loader_criteria` against real SQL are the things under test,
and a SQLite stand-in would be testing a different system. Guarantees that *can* be checked
without a database — no float column exists, a path cannot escape its org root — are checked
without one and never skip.

### DNS, if a hosted database hostname will not resolve

Some corporate resolvers refuse hosted-Postgres subdomains. `TIEOUT_DB_HOSTADDR=<ip>` passes
libpq's `hostaddr`, which skips the address lookup while still sending the URL's hostname for
SNI and TLS certificate verification — so the connection stays authenticated against the right
certificate. Leave it unset unless you need it.

### Windows

`psycopg`'s async mode cannot run on asyncio's `ProactorEventLoop`, which is the Python default
on Windows. `tieout.platform.session` sets the selector policy at import; no entry point has to
remember.

---

## 8. Verification

Migrations applied against a real Postgres (hosted Neon instance, PostgreSQL 18.6):

```
$ alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> c5333aa811a5, platform schema
```

Schema as it actually landed:

```
tables: alembic_version, disposition, entity, job, membership, organisation,
        policy_version, prior_decision, run, upload, verdict, work_item

--- any float/double column anywhere? ---
NONE

--- numeric columns ---
  disposition.amount:          NUMERIC(18,2)
  prior_decision.amount_delta: NUMERIC(18,2)
  verdict.amount_delta:        NUMERIC(18,2)
  verdict.confidence:          NUMERIC(5,4)
  verdict.fee_explained_delta: NUMERIC(18,2)
  work_item.amount:            NUMERIC(18,2)
```

Full suite with the database reachable:

```
$ pytest -q
157 passed, 11 skipped in 564.40s (0:09:24)
$ ruff check .
All checks passed!
```

Wall-clock note: the tenancy tests create and drop two organisations each and run against a
remote database, so the suite is slow over a network. Against a local Postgres it is far
quicker, and in CI the database tests skip.

---

## 9. What this layer does not do

- **No billing.** ADR-003 puts it out of scope: no payments, plans, checkout or metering.
- **No authentication.** Better Auth owns it. This layer consumes an org id.
- **No HTTP.** Routes belong to `tieout/api/`. Note for whoever builds them: ADR-003 forbids any
  route that would let a caller do what the agent's tool surface deliberately cannot. There is no
  `force` parameter in this package and none may be added.
- **No column-mapping UI.** `# ponytail: fixed ReconRiver schema; add a mapping step when a
  second real format appears.`
- **No second parser.** Uploads are validated by `tieout/ingest/reconriver.py`, which already
  fails loudly on a schema change and quarantines malformed rows. `upload.quarantined_row_count`
  and `upload.quarantine_reasons` are where its output is surfaced to the user.
- **No multi-entity consolidation.** `entity` exists and is referenced; rolling several up is a
  later feature, and the column being there now means it is data rather than a migration of
  every downstream table.
