# Tieout

Frontier models close the books by fabricating a transaction when they hit a mismatch they
can't resolve — [AccountingBench](https://accounting.penrose.com/) measured this at 15% of
overall balance for the best available models. Tieout doesn't ask an agent not to plug; it
removes the tool that could. Every posting requires a `match_id` resolving to an admissible,
evidenced match, so a period with unresolved breaks simply refuses to close — no override flag,
no env var, no force parameter, anywhere in the code.

See [`docs/SPEC.md`](docs/SPEC.md) for the full product specification, [`DESIGN.md`](DESIGN.md)
for the visual design system, and [`docs/RESEARCH.md`](docs/RESEARCH.md) for the evidence
(benchmarks, regulatory citations, market data) behind every claim above.

## Prerequisites

- Python >= 3.11
- [`uv`](https://docs.astral.sh/uv/) for dependency management

## Setup

```bash
uv sync                    # core dependencies
uv sync --all-extras       # + agent (deepagents/LangGraph) and obs (Neatlogs) extras
```

## Dataset

Tieout reconciles against the ReconRiver `month-end-close` scenario (CC BY 4.0). Fetch it with:

```bash
python scripts/fetch_dataset.py
```

(`scripts/fetch_dataset.py` and the on-disk layout it produces are owned by the `dataset-recon`
worker — see `docs/DATASET.md` once that lands.)

## CLI

```bash
tieout ingest    --scenario month-end-close       # hash + load the three source files
tieout policy    validate                         # schema + AS 2105 sanity check
tieout policy    show --version 2026.01-r3
tieout reconcile --period 2026-01                 # ingest -> blocking -> classify -> gate
tieout queue     [--blocking] [--aging]           # the exception queue
tieout review    <work_key> --approve|--reject|--reclassify <class> \
                 --as controller@acme --note "..."
tieout close     --period 2026-01                 # the close gate — the money shot
tieout score     --against ground-truth           # out-of-process scoring
tieout score     --baseline naive-llm|deterministic
tieout score     --passk 5                        # pass^k reliability
tieout audit     verify                           # hash-chain integrity
tieout audit     evidence <work_key>               # the evidence pack
tieout serve                                      # dashboard API on :8000
```

Every command accepts `--json` for structured output; this is the seam the dashboard and the
scoreboard both consume. As of this scaffold every command is a registered stub that raises
`NotImplementedError` naming the wave that owns its implementation (see `docs/PLAN.md`).

## Tests

```bash
uv run pytest -q
```

## A note on `policy.yaml`

The materiality figures shipped in `policy.yaml` (overall / performance / clearly-trivial
thresholds, tolerances, confidence tiers) are **illustrative values for a synthetic entity**.
They are not real materiality thresholds for any real company and must not be read as
accounting advice — see `docs/SPEC.md` section 19.
