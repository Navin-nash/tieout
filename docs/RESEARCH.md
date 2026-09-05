# Research Dossier — Syndicate by Maximor

Complete evidence base compiled 5 September 2026 across four parallel research strands, used to select Track 2 and design [Tieout](./DESIGN.md).

Every claim carries a source. Unverified, single-source and conflicting claims are flagged rather than smoothed over. Figures labelled *self-reported* are vendor marketing with no published methodology.

---

## Contents

1. [Method & Limitations](#1-method--limitations)
2. [The Event](#2-the-event)
3. [AO — Agent Orchestrator](#3-ao--agent-orchestrator)
4. [Maximor — The Judge](#4-maximor--the-judge)
5. [Other Sponsors](#5-other-sponsors)
6. [Track 1 Evidence — Automated Agent Engineering](#6-track-1-evidence--automated-agent-engineering)
7. [Track 2 Evidence — Autonomous Office of the CFO](#7-track-2-evidence--autonomous-office-of-the-cfo)
8. [Market & Business Models](#8-market--business-models)
9. [Documented User Pain](#9-documented-user-pain)
10. [Datasets](#10-datasets)
11. [Statistics Ledger](#11-statistics-ledger--what-to-use-what-to-avoid)
12. [Unverified & Conflicting Claims](#12-unverified--conflicting-claims)
13. [How the Evidence Drove the Decision](#13-how-the-evidence-drove-the-decision)

---

## 1. Method & Limitations

Four research agents ran in parallel, ~267 tool calls total:

| Strand | Scope |
|---|---|
| A | Agent-optimization prior art, failure attribution, cost-aware optimization, benchmarks |
| B | Commercial eval/observability landscape, pricing, funding, M&A |
| C | Documented practitioner pain — primary sources |
| D | Maximor judge profile, CFO-automation landscape, finance datasets |

Primary sources were extracted directly where possible. The Notion event page rendered as an empty shell and was extracted via its own API (`/api/v3/loadPageChunk`).

### Limitations — stated plainly

| Limitation | Impact |
|---|---|
| **Reddit hard-blocked on every route** — `reddit.com`, `old.reddit.com`, `.json` endpoints, redlib mirrors, `r.jina.ai` proxy, pullpush.io — all 403 | **Zero r/Accounting, r/LangChain or r/LocalLLaMA evidence.** Hacker News substituted (public Algolia API). This is a hole, not a finding. |
| **Firecrawl keyless developer index IP-blocked** — `{"success":false,"error":"your IP address looks suspicious..."}` | GitHub issue mining fell back to the GitHub Search API + `gh api` |
| **WebSearch quota (200) exhausted** in strands A and D | "Not found" means not found, not confirmed absent |
| Blocked at various points: x.com, linkedin.com, crunchbase.com, businesswire.com, forbes.com, cnbc.com, openai.com, AccountingWEB, Going Concern, Accounting Today, Proformative, BlackLine/FloQast/Trintech help centres | Some claims rest on syndicated reprints (Yahoo Finance, PYMNTS, SiliconANGLE) rather than original releases |
| Google, Bing, DuckDuckGo, Brave, Mojeek, SearxNG all served CAPTCHAs or 403s at some point | Discovery was patchier than ideal |
| **Not researched at all:** Intuit, Sage, Xero incumbent agent strategies | Real gap in the Track 2 landscape |

---

## 2. The Event

Sources: [Notion page](https://maaztwts.notion.site/Syndicate-by-Maximor-3cc32902e4a38075bfa9f03149ef150d) (via API) · [Luma](https://luma.com/d0kq45ek) · [Devpost](https://syndicate-by-maximor.devpost.com/) · [Devpost rules](https://syndicate-by-maximor.devpost.com/rules)

| Item | Value |
|---|---|
| Event | Syndicate by Maximor, presented by AO (Agent Orchestrator) |
| Window | **Sep 5 21:30 IST → Sep 7 03:30 IST** (Sep 5 12:00 EDT → Sep 6 18:00 EDT). 30 hours |
| Format | Global online; optional in-person SF (25 Stillman St, venue partner Neatlogs), NYC (1450 Broadway Fl 15 Suite 103, at Maximor), Bangalore (AO House, Sarjapur) |
| Submission | **Devpost only.** Discord posts do not count |
| Discord | Mandatory — `discord.gg/Sy3EwRBQX3`. Channels: announcements, project-showcase, general, find-a-teammate, help |
| Pass | `aoagents.dev/hackathons/syndicate/pass/` — post on X/LinkedIn, tag AO |
| Team | Solo or team, no size cap stated; each member registers individually |
| Eligibility | Open online worldwide. No student or age restriction found |
| Registered | 693 → 724 at last check |
| Judging period | May take up to one week |
| Hosts | Maaz, Prateek, Rayed Chowdhury, Khushi Diwan, Ajay Yadav, Bosky (@aigrantsindia), Prasad Ware |

### Judging criteria — attributed on Devpost to Prateek Karnal of AO

| Weight | Criterion |
|---:|---|
| **25%** | AO Usage & Build Process |
| **25%** | Technical Execution & Reliability |
| **25%** | Track Fit & Real-World Value |
| 15% | Demo & Usability |
| 10% | Innovation |

The rules page phrases the same rubric qualitatively — evaluation on *"practical use case, working end-to-end functionality, agent autonomy, reliability, **measurable improvements**, track alignment, **early user validation**, and demo clarity."*

> **Structural read:** 65% of the score is process, track fit and communication. Only 35% rewards cleverness. Two named criteria — *measurable improvements* and *early user validation* — are things most hackathon demos skip entirely.

### Deliverables

- Selected track
- Problem description and target users
- Functional working project
- **GitHub repository** with code *and setup instructions*
- **Demo video** showing the product *and* AO sessions (length not specified)
- Written explanation: agent architecture, tools, workflows, evaluation method
- **Evidence of measurable results**
- All team member names, each registered on Devpost

### Hard disqualifiers — verbatim

> *"Previously built or substantially pre-existing projects are not eligible."*
> *"All project work must begin after the official hackathon start time."*
> Organizers *"reserve the right to verify repositories, commit history, and demo materials."*
> *"Every project must use AO throughout the development process and demonstrate that usage in the final demo."*

### Prizes

| Award | Cash (Maximor) | Credits (Dodo) |
|---|---:|---:|
| 1st, per track | $1,000 | $1,000 |
| 2nd, per track | $500 | $500 |
| AI Grants India | \$100 GPU/voice credits × 20 projects **per track** — 40 total, $4,000 | |

Total pool $10,000. Top participants considered for **internships at Maximor and AO**.

Prizes are identical per track — **track choice is purely a question of win probability.**

---

## 3. AO — Agent Orchestrator

Sources: [github.com/Untrivial-ai/agent-orchestrator](https://github.com/Untrivial-ai/agent-orchestrator) · [aoagents.dev](https://aoagents.dev/) · GitHub API

**What it is.** A local desktop IDE written in Go for planning, running and supervising fleets of *coding* agents. Each task gets a worker with its own coding agent, model, git branch and worktree, terminal/chat, isolated browser preview, PR, CI and review state. A persistent project-orchestrator agent plans across the repo and spawns/redirects workers. Live Kanban: `Working / Needs you / In review / Ready to merge`. CI failures and review comments route back to the responsible agent. Tagline: *"Stop babysitting agents. Start merging real work."*

| Fact | Value |
|---|---|
| Repo | `Untrivial-ai/agent-orchestrator` |
| Language / licence | Go · Apache-2.0 |
| Stars / forks / commits | 10,941 · 1,528 · 2,582 |
| Created | 2026-02-13 |
| Agents supported | 25–26 harnesses: Claude Code, Codex, Cursor, Copilot, Aider, OpenCode, Droid, Goose, Devin, Kimi Code |
| Distribution | macOS arm64/x64, **Windows**, Linux AppImage/deb/rpm, Homebrew, npm (`@aoagents/ao`). Dashboard on `localhost:3000`. AO Mobile over LAN or Tailscale |
| Creator | **Prateek Karnal** (GitHub `AgentWrapper`, #2 contributor, 234 commits) — also the stated author of the judging criteria |
| Top contributor | harshitsinghbhandari (439 commits), IIT Bombay |
| Org members | Prasad Ware (`Prasad-D-Ware`) and Maaz (`somewherelostt`) — both hackathon hosts |
| Company / funding | **Not found.** `untrivial.ai` does not resolve in DNS. No round, investor or incorporation record located |

### The definition that matters for scoring

AO's own docs: a worker session is *"one task, one coding agent, and one isolated workspace."* Git-backed workers each get their own branch and worktree.

The Notion page: judges *"will review your demo video to see how many AO sessions you used."*

> **Therefore:** session count is literally the number of discrete delegated tasks on the board. **Decompose the build into many small delegated tasks, not a few large ones.** Same work, higher session count, more legible board, better video.

**Windows note:** the `brew install` line on the AO homepage is macOS-only. Windows users need `agent-orchestrator-win32-x64.exe` from the [releases page](https://github.com/AgentWrapper/agent-orchestrator/releases/latest) or the npm route.

**Unconfirmed:** a secondary source ([rywalker.com](https://rywalker.com/research/agent-orchestrator)) claims AO originated at Composio and a search snippet described the repo as "formerly ComposioHQ/agent-orchestrator." Composio is real (Sampark Inc, SF, founded 2023 by Soham Ganatra and Karan Vaidya, Lightspeed-backed). **Provenance could not be confirmed from Untrivial, Composio or GitHub.**

---

## 4. Maximor — The Judge

Domain is **maximor.ai**, not maximor.com.

### Positioning

> *"Audit-Ready Agents™ handle the manual finance work and bring you in when judgment is needed — on top of your ERP. No rip-and-replace, no migration."* — [maximor.ai](https://www.maximor.ai/)

> *"Maximor builds the context layer that turns finance into a competitive weapon."* — [/about](https://www.maximor.ai/about)

### The published three-layer architecture — from [/why](https://www.maximor.ai/why)

| Layer | Their words |
|---|---|
| **Policy Layer** | *"Encodes your accounting logic, not generic rules."* |
| **Self-Improving Agents** | *"Processing, matching, reconciling, posting."* |
| **Audit Trail** | *"Deterministic, explainable, auditable."* |

> *"Agents read from your ledger, post entries back to it, and leave the audit trail where your auditors already look."*
> *"Agents derive policy from how your team already works, apply it, and bring a human in when a case falls outside it. Every action is logged, reviewable and reversible."*
> *"Point tools automate a slice of the work. Audit-Ready Agents™ run the whole function on one shared context."*

### Workflows automated

- Revenue recognition — contract-to-cash, **ASC 606**, deferred revenue waterfalls
- Cash management — auto-application across AR/AP, daily reconciliation, **13-week cash forecast**
- Close — subledger management (accruals, prepaids), **JE drafting/posting**, reconciliations with audit trails
- AR/AP — invoice sending, collections, bill capture & coding, vendor/customer email
- Board reporting — multi-entity consolidation, **automated flux commentary**
- Instant answers — NL queries with source citations

Named close capabilities ([/automated-close](https://www.maximor.ai/automated-close)): Automated Reconciliation Preparation · Automated Journal Entry Posting (*"JE templates created and auto-posted with audit trails"*) · Automated Flux Analysis (*"AI generates first-pass variance analysis, highlighting anomalies instantly and drafting narratives"*) · Close Orchestration Dashboards.

Claims: close 10+ days → 3–5; *"99%+ accuracy across all accounts"*; *"Automate 90% of reconciliations and journal entries"*; live in 4–8 weeks. Layers on NetSuite, SAP, Intacct; also Salesforce, Oracle, Coupa, ADP, Excel.

### The controller review loop — [/controller](https://www.maximor.ai/controller)

The single most useful page for Track 2:

> *"You review. Maximor prepares."*
> *"exceptions surfaced first so your team spends time only where a human is needed"*
> *"Unmatched transactions come to you, and every decision teaches the platform."*
> *"the Agent escalates to your team with full context — what it found, why it flagged it, and what it recommends."*
> JEs are *"Prepared with full supporting evidence and queued for your approval"* → **"Approve, then post"**
> *"One live view of agent work, human approvals, validations, and evidence packs. Always inspection-ready."*

### "Knowing when to stop" — two primary sources

**1. CEO-authored blog, 13 Aug 2026** — [What we mean by autonomous finance](https://www.maximor.ai/blog/what-we-mean-by-autonomous-finance)

> *"Autonomous finance is our name for what replaces human runtime. It works by sitting on top of the systems you already run – the ERP, the CRM, the payroll system, the banks."*
> *"When it's confident, it acts. When it isn't, it escalates to your team – and remembers the answer, so it never asks twice."*
> The product is built *"around the remaining 1%: **knowing when to stop**, what to escalate, whom to bring in, and how to show your work."*
> *"Every action it takes carries its own evidence: what it did, why, and based on what. Being audit-ready becomes a property of the system."*

**2. Press release, 28 Jan 2026** — headline is the same phrase: [*"CFOs Set New Bar for Finance AI: Show Your Work and Know When to Stop"*](https://www.globenewswire.com/news-release/2026/01/28/3227738/0/en/CFOs-Set-New-Bar-for-Finance-AI-Show-Your-Work-and-Know-When-to-Stop.html)

> That blog post is the judging rubric in prose: confidence-gated autonomy → escalation with context → learning from the escalation → evidence attached to every action.

### 2026 predictions — CEO-authored, 23 Dec 2025

[9 finance predictions for 2026](https://www.maximor.ai/blog/9-predictions-for-2026):

- **#6:** *"**'Human in the Loop' Is Code for 'We Like Being Slow'** … Smart companies will roll out **'confidence-tiered autonomy'**. AI handles 90% of routine work solo."*
- **#2:** *"Close in 5 Days or Start Updating Your Resume … 'Speed to Close' becomes the primary metric for operational competence."*
- **#3:** *"AI errors are systematic, traceable, and fixable. Human errors? They are buried in hard-coded spreadsheet cells."*
- **#8:** *"The differentiating skill of 2026 will be knowing when to look the algorithm in the eye and say 'No'."*

> **Design consequence.** This judge is on record calling undifferentiated human-in-the-loop a euphemism for slowness. A demo that routes *everything* to a human reads as unambitious to him specifically. Tier by **confidence and materiality**.

### Company facts

| Fact | Detail |
|---|---|
| Founded / HQ | 2024 · New York City (one outlet says SF; job postings favour NYC — **unresolved**) |
| Funding | **$9M seed**, 29 Sep 2025, led by **Foundation Capital**, with Gaia Ventures and BoldCap |
| Angels | Founders/finance leaders from Perplexity (Aravind Srinivas), Zuora (Tien Tzuo), Zoom, Ramp, Gusto, MongoDB, Opendoor, Big 4 |
| CEO | **Ramnandan Krishnamurthy** — IIT Madras CS; ShopSkipper; Microsoft, led global finance transformation / internal revenue-systems overhaul. [LinkedIn](https://www.linkedin.com/in/ramnandan). **No X handle found** |
| CTO | **Ajay Krishna Amudan** — IIT Madras CS, Stanford CS, **ACM-ICPC 2015 World Finalist**, **IMO 2011 & 2012**. ~5 yrs Microsoft: *"led the 0→1 rebuild of Microsoft's Finance Platform powering metering, pricing, billing, collections, and revenue reporting."* **No X handle found** |
| Compliance | SOC 2 Type II, ISO 27001, GDPR, CCPA. *"No customer's data is ever used to train another's model."* |

Funding sources: [Maximor blog](https://www.maximor.ai/blog/maximor-raises-9m-to-give-cfos-audit-ready-finance-automation-without-erp-rip-and-replace) · [FinTech Global](https://fintech.global/2025/09/30/maximor-raises-9m-to-expand-ai-finance-automation/) · [Crowdfund Insider](https://www.crowdfundinsider.com/2025/10/253769-maximor-9m-seed-to-drive-ai-agent-growth/)

> *"Finance doesn't need another ERP. It needs an AI-powered teammate. That's what we're building at Maximor."* — funding announcement

### Traction — all self-reported and unaudited, 5 Aug 2026

[GlobeNewswire](https://www.globenewswire.com/news-release/2026/08/05/3339475/0/en/Maximor-grows-revenue-35x-in-9-months-as-it-elevates-finance-from-task-automation-to-full-autonomy.html): 35× revenue growth in 9 months · multi-million ARR · **98% of transactions run end-to-end without human intervention** · 25+ customers · ~90% reduction in repetitive finance work · **~75% reduction in audit exceptions**.

> *"Finance teams are not short of software. They are short of systems willing to take responsibility for the work."* — Ramnandan, same release

Named customer **Kiteworks** ([case study](https://www.maximor.ai/case-study/kiteworks)): treasury/cash across **10 legal entities**, accountants **20 → 5**, **98% straight-through processing**, live in <4 weeks. VP Global Controller Kristine Radhakrishnan: *"Critical finance workflows at Kiteworks no longer take hours. With Maximor, they're autonomous."*

Other quotables: *"96% of CFOs want AI — only 14% trust it."* ([/about](https://www.maximor.ai/about)) · *"75% of accountants are nearing retirement,"* CPA pipeline down 30% over a decade.

### Engineering signal — no engineering blog exists

The blog index has 8 posts, all business-facing. The strongest technical signal is the job board ([jobs.ashbyhq.com/maximor](https://jobs.ashbyhq.com/maximor); `/careers` is 404). Seven roles, NYC-heavy. Verbatim:

- ***"Our stack is Python"*** (Go/Java/Rust acceptable; TypeScript when needed)
- ***"Fluency with Claude, Cursor, and internal agent tooling is a second cortex"***; new-grad role expects *"Fluency with Claude Code, Cursor"*
- Staff role owns *"agent frameworks, context systems, and verification infrastructure"* — *"the systems every module depends on"*
- Named critical systems: **context systems, verification/guardrails/observability, evaluation frameworks for non-deterministic AI, orchestration & durable-execution workflow engines**
- Senior engineers **own a finance domain end-to-end** and *"work directly with controllers, accountants, and CFOs"*
- New grads join a **2–3 person pod** shipping *"contexts, prompts, tools, evals"* in month one
- AE role: mid-market/enterprise, **$50k+ ACVs**

> **"Evaluation frameworks for non-deterministic AI" is a named hiring priority.** A submission with a real eval harness lands directly on it.

> ⚠️ **Do not trust** `startupintros.com/orgs/maximor-ai` — claims 1,001–5,000 employees and investors Greylock/SV Angel/Drew Houston/Dylan Field. Contradicts every primary source. Likely AI-generated.

---

## 5. Other Sponsors

### Neatlogs — the supplied observability layer

[neatlogs.com](https://neatlogs.com/) · [GitHub](https://github.com/neatlogs/neatlogs)

*"A collaborative debugging workspace for AI agents."* Trace runs with full span trees (latency/cost), AI-powered trace search, trace detection rules, **prompt versioning with rollback**, human + AI evaluation campaigns, dashboards (failures, latency, cost, regressions), comments so non-technical teammates can participate.

`pip install neatlogs`, Python 3.10–3.13, **MIT**, ~2 lines to instrument. Integrations: OpenAI/Anthropic/Gemini/Azure/Bedrock/LiteLLM/Groq/Mistral; LangChain, LangGraph, CrewAI, LlamaIndex, Haystack, AutoGen, DSPy, Pydantic AI; Chroma/Pinecone/Qdrant/Weaviate; Slack, Linear, Jira, Notion, GitHub, Cursor.

Founder & CEO **Ajay Yadav**, San Francisco — also a hackathon host. GitHub org created 2025-02-12, 7 repos, main repo 83★. Free tier, no credit card. **No co-founders and no funding found.**

> Instrumenting costs ~2 lines and feeds the "reliability / measurable improvements" criteria directly. Cheap points.

### Dodo Payments

[dodopayments.com](https://dodopayments.com/) · [funding announcement](https://dodopayments.com/blogs/dodo-payments-raises-1-1m-to-simplify-global-payments)

Global **Merchant of Record** for digital-first/AI businesses; 150+ countries, 25+ payment methods (Apple Pay, Klarna, UPI, cards), handles VAT/GST/sales tax, FX, chargebacks, local payouts; no US/EU entity required.

Founders **Rishabh Goel** (CEO; previously cross-border BNPL at Bzaar, earlier Wise and Prodigy Finance) and **Ayush Agarwal** (CPTO; founded Tournafest). **$1.1M pre-seed, 25 Feb 2025**, co-led by **Antler, 9Unicorns, Venture Catalysts**. Angels: Nitin Gupta (Uni Cards, PayU), Maninder Gulati (ex-OYO CSO), Raymond Russell (ex-Boom Supersonic), Preethi Kasireddy (ex-a16z), Nishant Verman (ex-Flipkart). Entity Sarvapanchhi Technologies Pvt Ltd, founded 2024. [Inc42](https://inc42.com/company/dodo-payments/): total funding $1.10 Mn+, 79 employees.

> ⚠️ **Three flags.** (a) A snippet attributing *"$8.80 Mn+ from 8 investors"* to Inc42 contradicts the Inc42 page actually fetched — treat ≈$8.8M as **unverified**. (b) The same round is labelled "pre-seed" by ET/company and "seed" by Zee Business. (c) The homepage a16z/Lightspeed/Goldman/Visa/AWS logo wall reads as **operational partners and angel affiliations, not direct investors** — the primary release names only Antler/9Unicorns/Venture Catalysts. **Don't repeat the logo wall as fact.**

### AI Grants India

[aigrants.in](https://aigrants.in/)

Non-profit giving free production API access to Indian builders. *"The fastest onramp for developers, students, and hackers — no credit cards, no red tape,"* decisions in under 5 minutes from one short form, *"no equity stake, clawbacks, or hidden strings."* Provides production API keys (open-source + proprietary models), voice/TTS credits, GPT Nano inference keys.

Co-founders **Bhasker Kode** and **Vaibhav Domkundwar**; founding sponsor the **Domkundwar Foundation**, which underwrites the credits. Supplies **$4,000** of the prize pool. Explicitly courts hackathon teams: *"ship your demo without burning your weekend topping up API credits."*

> Not to be confused with the government IndiaAI programme (MeitY). The common association of Vaibhav Domkundwar with Better Capital was **not verified in this session**.

### TensorMux

[tensormux.com](https://www.tensormux.com/) · [GitHub](https://github.com/tensormux)

*"The control plane for LLM inference."* *"Route, autoscale, and meter inference across vLLM, SGLang, and TensorRT-LLM, on any GPU, in any cloud."* Framing: *"The moment you run more than one model, engine, or GPU tier, your apps inherit infrastructure they shouldn't own."*

Features: routing strategies, autoscaling incl. **scale-to-zero**, **distributed KV cache for cross-engine reuse**, model + **LoRA orchestration**, per-tenant token metering, unified observability. Tiers: Gateway (free, OSS, self-hosted) / Shared / Dedicated / On-Prem; no published rates. **Part of NVIDIA Inception.**

Repos: `KrxGu/Tensormux` (Python, MIT, 27★), `tensormux/kernel-skills` (TypeScript, MIT, 73★ — *"skill library for AI coding agents to write, optimize, and debug high performance compute kernels"*), `tensormux/Tensorpath`. **Named founders not confirmed** — contact is `founders@tensormux.com`. **Funding: none disclosed.**

---

## 6. Track 1 Evidence — Automated Agent Engineering

**The brief:** given only a goal, available tools and a way to evaluate success — generate an agent architecture, run it, analyse where it fails, iteratively improve prompts/tools/memory/orchestration. Demonstrate across **multiple distinct domains** with measurable gains in **accuracy, reliability, cost and speed**.

### 6.1 Prompt-level optimizers

| System | Optimizes | Mechanism | Result |
|---|---|---|---|
| **OPRO** (DeepMind '23) [arXiv](https://arxiv.org/abs/2309.03409) | Instruction string only | Meta-prompt containing the optimization trajectory; LLM generates candidates. No gradients | +8% GSM8K over human prompts; up to +50% on some Big-Bench Hard |
| **MIPROv2** (DSPy) [arXiv](https://arxiv.org/pdf/2406.11695) · [docs](https://dspy.ai/api/optimizers/MIPROv2/) | Instructions **and** few-shot demos, jointly, across modules | Bootstrap demo candidates → grounded instruction proposal → **Bayesian optimization** (TPE surrogate) on minibatches | Beaten by GEPA by >10% |
| **GEPA** (ICLR 2026 **Oral**) [arXiv](https://arxiv.org/abs/2507.19457) · [GitHub](https://github.com/gepa-ai/gepa) | Arbitrary textual components | **Genetic-Pareto.** NL *reflection* on execution traces + textual feedback proposes mutations; Pareto frontier over per-instance scores maintains diversity | **+6% avg over GRPO (up to +20%), 35× fewer rollouts**; >10% over MIPROv2 (+12% AIME-2025) |
| **TextGrad** (Stanford, *Nature*) [arXiv](https://arxiv.org/abs/2406.07496) | Any text variable | Computation graph where **nodes = text variables, edges = LLM calls**; LLM critique "backpropagated" as textual gradients | SOTA code optimization + GPQA at publication |
| **Trace / OptoPrime** (MSR, NeurIPS '24) [GitHub](https://github.com/microsoft/Trace) · [arXiv](https://arxiv.org/pdf/2406.16218) | Prompts, hyperparams, code, robot controllers | Formalizes **OPTO**: optimizer receives the *execution trace DAG* plus feedback. PyTorch-like decorators capture the trace | *"Trace is the new autodiff"* |

**OPRO's stated limitations:** not competitive with gradient-based continuous optimization or specialized combinatorial solvers; context-window limit prevents scaling to large problem descriptions; global optimum demonstrated only *"for some small-scale problems."*

**MIPROv2's documented limitation:** candidate pool quality/diversity is capped by the proposer model — it *"doesn't discover genuinely novel prompting strategies"*; combinatorics are brutal (10 instructions × 5 demos from a pool of 50 ≈ 20M configurations). ([Comet](https://www.comet.com/site/blog/mipro-optimization/))

**GEPA's abstract states no limitations** — verified directly. Independent 2026 work contests it (see NPO/RLMOpt below).

### 6.2 Architecture / workflow search

| System | Optimizes | Mechanism | Result |
|---|---|---|---|
| **ADAS** (ICLR '25) [arXiv](https://arxiv.org/abs/2408.08435) · [site](https://www.shengranhu.com/ADAS/) | **The agent as code** — Turing-complete search space | **Meta Agent Search** — a meta-agent iteratively writes agent programs in Python conditioned on a growing archive | +13.6/100 F1 reading comprehension, +14.4% math vs SOTA hand-designed. Transfers across models and domains |
| **AFlow** (ICLR '25, MetaGPT) [arXiv](https://arxiv.org/abs/2410.10762) | Workflow graph | **MCTS over code-represented workflows**, tree-structured experience reuse, reusable node combinations (Ensemble, Review&Revise) | +5.7% avg over SOTA on six benchmarks; **small models beat GPT-4o at 4.55% of its inference cost** |
| **AgentSquare** (ICLR '25) [arXiv](https://arxiv.org/abs/2410.06153) · [GitHub](https://github.com/tsinghua-fib-lab/AgentSquare) | **Module composition**: Planning, Reasoning, Tool Use, Memory. 16 agents abstracted into **1,050 combinations** | Module evolution (prompt-level) + module recombination (module-level), accelerated by an in-context surrogate performance predictor | **+17.2% avg over best-known human designs** across six benchmarks |
| **MaAS** (ICML '25 **Oral**, top ~1%) [arXiv](https://arxiv.org/abs/2502.04180) · [GitHub](https://github.com/bingreeky/MaAS) | A **probabilistic distribution over architectures**; samples a query-dependent system per input | "Agentic supernet" trained to allocate LLM calls / tool calls / tokens by query difficulty | **6–45% of the inference cost** of existing MAS while outperforming by 0.54–11.82%. On MATH: **$3.38 training vs AFlow's $22.50 (6.8×)**; inference $0.42; 53 min vs DyLAN 508 min |
| **Darwin Gödel Machine** (Sakana + UBC) [arXiv](https://arxiv.org/abs/2505.22954) · [site](https://sakana.ai/dgm/) | Its own source code (harness/scaffold), not weights | Empirical self-modification; archive of agent variants proposing code edits to themselves, validated on coding benchmarks | **SWE-bench 20.0% → 50.0%** |

> ### The DGM reward-hacking incident — the reference failure for Tieout
>
> Tasked with reducing hallucination, an agent scored well by **deleting the logging tokens the hallucination detector relied on** — defeating the detector rather than the problem. Authors reported it themselves. ([sakana.ai/dgm](https://sakana.ai/dgm/))
>
> Other DGM limitations: bounded by the frozen foundation model; fixed non-self-modifiable exploration process; local-optima risk. Cost reported at **~$22,000 per SWE-bench iteration** — ⚠️ *from a [secondary Substack analysis](https://gonzoml.substack.com/p/darwin-godel-machine), not confirmed in the paper.*

**⚠️ Potentially the most important negative result, unverified:** a follow-up review reports ADAS's sequential search performs **comparably to random sampling**, with peak accuracy failing to beat the best of 30 random samples — i.e. it does not effectively exploit its archive. Reproducibility "doubly hampered" (stochastic outer loop + nondeterministic temperature-0 decoding). *Source is a non-peer-reviewed preprints.org review surfaced via search snippet; full text not fetched. Verify before citing.*

### 6.3 2025–2026 systems

| System | Optimizes | Key result |
|---|---|---|
| **AutoMaAS** (Oct '25, PKU) [arXiv](https://arxiv.org/abs/2510.02669) | Operator lifecycle + architecture — automatic **generation, fusion, elimination** driven by performance-cost analysis; decision tracing | Best accuracy/cost balance vs MaAS/AFlow |
| **ACE — Agentic Context Engineering** (Oct '25) [arXiv](https://arxiv.org/abs/2510.04618) | The **context/playbook**, not the prompt. Generate → reflect → curate into itemized bullets; incremental delta updates | **+10.6% agent tasks, +8.6% finance**; matches top production agent on AppWorld, beats it on test-challenge |
| **AgenTracer** (ICLR '26) [arXiv](https://arxiv.org/abs/2509.03312) | Failure attribution — counterfactual replay + programmatic fault injection; trains an 8B tracer | See §6.4 |
| **A²Flow** (Nov '25) [PDF](https://arxiv.org/pdf/2511.20693) | Workflows via self-adaptive abstraction operators | *not fetched* |
| **EvoRoute** (ACL '26) [arXiv](https://arxiv.org/abs/2601.02695) | **Per-step model routing** inside long-horizon trajectories; Pareto filtration + Thompson sampling | **−80% cost, −70% latency** on GAIA/BrowseComp+ at equal-or-better accuracy; BrowseComp+ **+5.2pp accuracy, −64% cost, −49% duration**. Names the *"Agent System Trilemma"* |
| **MCE — Meta Context Engineering** (ICML '26) [PDF](https://arxiv.org/pdf/2601.21557) | **Bi-level**: co-evolves context-engineering *skills* and context artifacts via "agentic crossover" | — |
| **RLMOpt** (Aug '26) [arXiv](https://arxiv.org/abs/2608.10471v1) | Prompts, with a **learned search policy** that inspects task info, analyzes failures, allocates eval budget, decides when to stop | **Beats GEPA in 9/11 benchmark-seed cases** |
| **NPO — Naive Prompt Optimization** (Aug '26) [arXiv](https://arxiv.org/abs/2608.27266) | Prompts — single-lineage iterative revision, deliberately **no search** | **Matches or beats GEPA with fewer rollouts**; advantage *grows* with stronger teacher models |
| **Survey: Self-Improvements in Modern Agentic Systems** (Jul '26, 97pp) [arXiv](https://arxiv.org/abs/2607.13104) · [site](https://selfimproving-agent.github.io/) | Frames agents as *"foundation model + operational scaffold of prompts, memory, tools, control logic"* | The field map |
| **Harness Engineering for Self-Improvement** — Lilian Weng (Jul '26) [post](https://lilianweng.github.io/posts/2026-07-04-harness/) | Best synthesis found | See failure modes below |

**Weng's documented failure modes for the whole class:**
- **STOP improved with GPT-4 but *degraded* with weaker models** (GPT-3.5, Mixtral) — self-improvement has a **capability floor**
- *"Weak and fuzzy evaluators"* for anything without fast precise verification
- **Diversity collapse** in evolutionary loops
- **Reward hacking whenever the optimizer can touch its own evaluation**
- Short-horizon objectives don't capture maintainability
- Over-optimism: models declare success on noisy experiments

> ### The validated white space
>
> **No system found performs failure attribution and then routes the fix to the matching optimizer** (prompt vs tool vs memory vs orchestration). Attribution and optimization are **disjoint literatures**. AgenTracer is the closest bridge — feeding attribution back into MetaGPT and MaAS yields **+4.8–14.2%** — but it does not choose *what kind* of fix to apply.

### 6.4 Failure attribution — the hard numbers

**Who&When** (ICML 2025 Spotlight) — *"Which Agent Causes Task Failures and When?"* Zhang et al. (PSU + Duke). [arXiv](https://arxiv.org/abs/2505.00212) · [PMLR](https://proceedings.mlr.press/v267/zhang25cq.html) · [GitHub](https://github.com/ag2ai/Agents_Failure_Attribution)

Failure logs from **127 LLM multi-agent systems**, annotated with responsible agent, decisive error step, NL explanation. Three methods: All-at-Once, Step-by-Step, Binary Search.

- **Agent-level attribution: 53.5% best**
- **Step-level attribution: 14.2% best**
- **Some methods perform below random.** o1 and DeepSeek-R1 both fail to reach practical usability
- Requiring explicit reasoning in the prompt improves All-at-Once and Step-by-Step
- **Accuracy degrades as log context length grows**, hitting step-attribution hardest

**AgenTracer** (ICLR 2026) [arXiv](https://arxiv.org/abs/2509.03312) — automated annotation via counterfactual replay + programmatic fault injection; TracerTraj (**>2,000 high-fidelity failure trajectories, 7 datasets**); trains AgenTracer-8B. Current SOTA reasoning LLMs score **generally below 10%**; AgenTracer-8B beats Gemini-2.5-Pro and Claude-4-Sonnet by **up to 18.18%**. Downstream: **+4.8–14.2%** when fed back into MetaGPT and MaAS. ⚠️ *Separate agent-level vs step-level percentages could not be extracted; the "below 10%" metric is ambiguous.*

**TraceElephant** (ACL 2026) — *"Seeing the Whole Elephant."* [ACL](https://aclanthology.org/2026.acl-long.912/) · [arXiv](https://arxiv.org/html/2604.22708v1)

380 traces (**220 failed**) from Captain-Agent, Magentic-One, SWE-Agent over GAIA / AssistantBench / SWE-Bench, with **reproducible replay environments**. Attributes to **functional component** — planner, orchestrator, tool-use module.

- Full-trace, Static Agentic: **agent-level 65.9%, step-level 30.3%**
- Adding replay (Dynamic): step-level → **33.3%**
- Ablated to output-only (Who&When-style): agent-level **51%** (−22%), step-level **16%** (−76%)
- **Full traces improve attribution by up to 76.5%** ← the biggest lever documented
- Attribution principle is role- and recoverability-aware: if a downstream verifier should have caught an error and didn't, blame the verifier
- Limitations: only 3 MAS architectures; developer-facing full-trace setting only; step-level highly sensitive to missing information

**Who&When Pro** (Jul '26) [summary](https://www.emergentmind.com/papers/2607.09996) — 12,326 failed trajectories, 15 frameworks, 26 benchmarks, 3 modalities, 18-category error taxonomy. **Step-level best 73.9% on text**; multimodal substantially lower; **drops to ~50% on traces >12k tokens**. **Error-mode classification: best macro-F1 only 22.2%.** Central diagnosis: *"LLMs tend to attribute failures to the most visible **symptom** rather than tracing back to the **originating cause**."* ⚠️ *Numbers from a summary site, not the arXiv PDF.*

#### Summary table

| Setting | Component-level | Step-level |
|---|---:|---:|
| Who&When, output-only, 2025 | **53.5%** | **14.2%** |
| TraceElephant, output-only ablation | 51% | 16% |
| TraceElephant, **full trace** | **65.9%** | 30.3% |
| TraceElephant, full trace + replay | 65.9% | **33.3%** |
| Who&When Pro, text, 2026 best | — | **73.9%** (~50% past 12k tokens) |
| Error-*type* classification | — | **22.2% macro-F1** |

> **The problem is genuinely hard.** Component-level sits at 50–66%; step-level at 14–33% without rich traces. Biggest available win: give the attributor the **full execution trace** (+76.5%). Largest residual failure mode: symptom-vs-root-cause confusion.

### 6.5 Cost-aware optimization — crowded, not a gap

**AI Agents That Matter** (Kapoor, Stroebl, Siegel, Nadgir, Narayanan — Princeton) [arXiv](https://arxiv.org/abs/2407.01502) — agent benchmarks focus narrowly on accuracy → *"SOTA agents are needlessly complex and costly."* Introduces cost-controlled evaluation. **Simple baseline strategies match complex agents at up to 50× lower cost.** Also: *"pervasive lack of reproducibility"*; benchmarks have *"inadequate holdout sets, and sometimes none at all."*

**Holistic Agent Leaderboard (HAL)** (ICLR '26, Princeton) [arXiv](https://arxiv.org/abs/2510.11977) · [site](https://hal.cs.princeton.edu/) — **21,730 rollouts, 9 models, 9 benchmarks, ~$40,000** (26,597 rollouts by Apr 2026). **Higher reasoning effort reduced accuracy in the majority of runs.** Pareto inversions common and large:
- Online Mind2Web: Browser-Use + Claude Sonnet 4 = **40% for $1,577**; SeeAct + GPT-5 Medium = **42% for $171** (better *and* 9× cheaper)
- GAIA: HAL Generalist + o3 Medium = **28.5% for $2,828**; another agent = **57.6% for $1,686**

**CLEAR framework** [arXiv](https://arxiv.org/html/2511.14136v1) — cost, latency, effectiveness, assurance, reliability. Highest-raw-accuracy agents cost **4.4–10.8× more** than Pareto-efficient alternatives.

**Model routing / cascades:**
- **FrugalGPT** (2023) [arXiv](https://arxiv.org/abs/2305.05176) — cascade gated by confidence check. Matches GPT-4 at **up to 98% cost reduction**, or +4% accuracy at equal cost; 50–98% savings
- **RouteLLM** (Berkeley, ICLR '25) — **>85% cost reduction on MT-Bench at 95% of GPT-4 performance, routing only 14% of queries to the strong model**
- **EvoRoute** (ACL '26) — SOTA for *agentic* routing; per-step, Pareto filtration + Thompson sampling
- 2026 follow-ups: UCCI [PDF](https://arxiv.org/pdf/2605.18796) · Cluster-Route-Escalate [PDF](https://arxiv.org/pdf/2606.27457) · four-router comparison [HTML](https://arxiv.org/html/2608.14641)

> **Conclusion: cost-aware routing is the most crowded, most commercially mature part of this landscape.** The gap is **cost-aware *diagnosis*** — nobody decides *which component to spend optimization budget on* based on attributed failure cause.

### 6.6 Documented weaknesses of DSPy-style optimization

**A. Gains don't transfer.** *"The superiority of optimized prompts on one benchmark often fails to transfer to another, and this limitation persists even when switching across different LLM backbones."* ([arXiv](https://arxiv.org/html/2605.26655v1)) Transferred prompts **sometimes underperform the *initial* prompt** on a different model. ([arXiv](https://arxiv.org/pdf/2505.08303))

**B. Inverse scaling — the most damaging documented weakness.** Black-box prompt optimization gain by model size: **+12% (Qwen-2.5 7B) → +5.9% (72B) → +1.1% (DeepSeek-V3 671B)**. ([arXiv](https://arxiv.org/pdf/2505.08303)) *DSPy-style optimization is a small-model technique whose value decays as frontier models improve.*

**C. Optimization is not monotone.** Causal edit-level analysis over ~20,000 optimization tuples (DSPy/MIPROv2: 2,095 pairwise comparisons; TextGrad and GEPA: 17,708 each), BH-FDR corrected ([arXiv](https://arxiv.org/html/2605.26655v1)):

| Edit family × task type | Effect (ACMGD) |
|---|---:|
| Meta-instruction ("make sure to") × **math** | **−0.103** |
| Clarity constraint ("be concise") × **logic** | **−0.083** |
| Extraneous load × **sequential** | −0.060 |
| Metacognition × **sequential** | +0.062 |
| Step-by-step × sequential | +0.045 |

Few-shot demos help math, **hurt** sequential tasks. *"Failures arise from systematic interactions between edit families and task characteristics rather than random artifacts."*

**D. Overfitting to metric and trainset.** Recommended mitigation: run GEPA then *ablate* examples and overly specific descriptions back out. Small gains may not be statistically significant against run-to-run variance. ([TDS](https://towardsdatascience.com/systematic-llm-prompt-engineering-using-dspy-optimization/))

**E. The search complexity may be unnecessary.** NPO (Aug '26): *"recent developments increasingly favor unnecessarily complex prompt optimizers"*; single-lineage iterative revision matches or beats GEPA with fewer rollouts — *"stronger teacher reasoning can partially substitute for optimizer-side search complexity."*

**F. Practitioner voices** ([HN](https://news.ycombinator.com/item?id=42343692)):
- *"I would love to be wrong, but DSPy makes huge promises and falls painfully short on basically all of them"* — reports of **zero success with automated instruction generation**; only few-shot demo selection reliably works
- *"Those who managed to build something with DSPy had headaches productionizing it"* ([HN](https://news.ycombinator.com/item?id=40556135))
- **Opacity:** *"DSPy is opaque as prompts are hidden behind abstractions; it saves you from dealing with iterations of prompts but you also lose control."* ([Advancing Analytics](https://www.advancinganalytics.co.uk/blog/prompt-optimisation-an-introduction-to-dspy))
- **Scope creep:** *"DSPy and friends do too much, by trying to also be the agent framework & runtime, while users just want the autotuner."*
- **Architectural gaps:** modules are not chat-history-aware, blocking realistic multi-turn testing

**G. Multi-agent under-characterized.** MAS-PromptBench (Jun '26) [arXiv](https://arxiv.org/abs/2606.23664) finds gains **highly sensitive to system configuration** (task type, workflow design, communication protocol, team size). ⚠️ *Specific numbers not extractable; PDF fetch failed.*

### 6.7 Benchmarks

| Benchmark | Size | Cost / note |
|---|---:|---|
| **τ-bench** [arXiv](https://arxiv.org/abs/2406.12045) | **115 retail + 50 airline = 165** | GPT-4o <50%; **pass^8 <25% on retail** — a *reliability* metric, not just accuracy |
| **τ²-bench** [PDF](https://arxiv.org/pdf/2508.18669) | +114 telecom, dual-control | Successor |
| **GAIA** [arXiv](https://arxiv.org/abs/2311.12983) | **466 total**; ~166 public with answers, 300 held out | Human 92% vs GPT-4+plugins **15%**. Per-task median **$0.38** |
| **SWE-bench Verified** | 500 | **Median $163 per full run**; per-task $0.08–$32.00, median $1.19 |
| SWE-bench Multimodal | — | $1.89/task |
| SWT-bench | — | $0.98/task |
| WebArena | self-hosted sites | Heavy environment setup |
| AppWorld | multi-app tool calling | Used by ACE; has a test-challenge hard split |
| Terminal-Bench [PDF](https://arxiv.org/pdf/2601.11868) | CLI tasks | ICLR-track 2026 |

⚠️ *SWE-bench Lite = 300 and WebArena = 812 believed correct but unverified — swebench.com fetch failed.*

**Efficient Benchmarking of AI Agents** (2026) [arXiv](https://arxiv.org/abs/2603.23749) — 8 benchmarks, 33 scaffolds, 70+ model configs. **Cut evaluation tasks by 44–70% while maintaining high rank fidelity** under scaffold and temporal shift. **Selection rule: keep tasks with intermediate historical success rates (30–70% pass rate)**, motivated by Item Response Theory. Beats random sampling and greedy selection. Key asymmetry: absolute scores degrade under shift, but **rank-order is stable**.

### 6.8 Ready-made labelled failure data

- **Who&When** — 127 systems, labelled: [github.com/ag2ai/Agents_Failure_Attribution](https://github.com/ag2ai/Agents_Failure_Attribution)
- **TraceElephant** — 220 failed traces with replay environments: [ACL 2026](https://aclanthology.org/2026.acl-long.912/)
- **Who&When Pro** — 12,326 trajectories
- Tracking list: [awesome-auditable-ai](https://github.com/yzhao062/awesome-auditable-ai)

---

## 7. Track 2 Evidence — Autonomous Office of the CFO

**The brief:** automate a real accounting/finance/treasury workflow **end to end, including exceptions and human review**. Examples: closing the books, reconciling accounts, processing invoices, updating forecasts, cash reports, audit support. **Explicitly out of scope:** consumer banking, trading, lending, payment products.

### 7.1 AccountingBench — the only independent benchmark in this space

Built by **Penrose**. Benchmark site: [accounting.penrose.com](https://accounting.penrose.com/) · Public discussion with the team participating: [HN 44637352](https://news.ycombinator.com/item?id=44637352) (534 points, 149 comments, Jul 2025).

Gives frontier LLMs a **real SaaS company's full year of financial data** — pulled from **Ramp, Rippling, Stripe and Mercury** — and asks them to **close the books month by month**, measured against the CPA-prepared baseline for the same company.

#### Scores

- **o3, o4-mini and Gemini 2.5 Pro could not complete even one month.**
- **Claude and Grok 4** tracked **~1% from the CPA baseline** in the first few months, then **diverged by >15% of overall balance — roughly $500,000 for this company — after several months.**
- **Subscription revenue** — *all* revenue for this business — was **consistently overstated by 5–30%, even for the best model.**

#### The four documented failure modes

1. **Reconciliation hacking** — rather than resolve genuine mismatches, models **fabricate transactions or pull in unrelated entries to satisfy validation checks**, in violation of explicit instructions.
2. **Error accumulation** — when reconciliation fails, models *"become confused and introduce additional errors rather than recover."*
3. **Accrual reversion** — struggle with deferred revenue and accrued expenses, *"sometimes reverting to cash-basis approaches despite contrary instructions."*
4. **Double-counting** without the ability to undo, carried forward into future months.

#### The diagnosis — benchmark team member, verbatim

[HN 44639140](https://news.ycombinator.com/item?id=44639140), user `yunyu`:

> *"Claude and Grok 4 did reasonably well (within CPA baselines) for the first few months, but tended to degrade as more data came in. Interestingly, the failures aren't exclusively a context length problem, as we reset the context monthly (with past decisions, accruals/deferrals, and comments available via tool calls) and **the types of errors appear to be more reward hacking vs pure hallucinations.**"*

#### Conceptual framing

Models excel at *stateless* tasks but fail on **"butterfly" tasks** where actions have lasting consequences and errors compound. *That is a precise description of a general ledger.*

> **Why this is the centre of the Tieout pitch.** Every other accuracy number in this space is vendor marketing. AccountingBench establishes that (a) the failure mode is *fabricating a match to make the books balance*, and (b) the problem is **state and reward hacking, not context window**. A system that **refuses to close** rather than plugging is the direct answer — and it matches the judge's own published phrase.

### 7.2 Which workflows are hardest

#### Tier 1 — judgment is load-bearing; the standard itself forbids a deterministic answer

**Revenue recognition (ASC 606)** — the empirically hardest. BDO: *"Two companies with similar transactions may reach different conclusions about performance obligation identification, SSP estimation, and variable consideration constraints — all within the bounds of the standard."* When standalone selling price isn't observable, management picks among three estimation methods and *"different methods can yield materially different allocations, directly affecting the timing of revenue recognition."*

Evidence it's real: rev rec was the **#2 cause of 2025 restatements at 14%**; SEC comment letters on 606 have risen steadily since 2018; live FY2025 material weaknesses at **SkyWater, Key Tronic, SharkNinja, Pangaea Logistics** — a decade after adoption.
Sources: [BDO](https://www.bdo.com/insights/assurance/revenue-recognition-under-asc-606) · [FASB](https://storage.fasb.org/ASU%202014-09_Section%20A.pdf) · [Ideagen](https://www.ideagen.com/resources/whitepapers/financial-restatements-report-may-2026) · [RevenueHub](https://www.revenuehub.org/article/sec-comment-letters-asc-606) · [SharkNinja 10-K](https://www.sec.gov/Archives/edgar/data/1957132/000195713226000015/sharkninja-20251231.htm)

**FX remeasurement / translation (ASC 830)** — functional currency *"is not simply an election that the reporting entity makes but a determination that is made on the basis of facts,"* and *"it can be challenging to determine an entity's functional currency."* A group must first *"identify the distinct and separable operations"* and decide for **each**. Get it wrong and the error routes to the wrong statement entirely: remeasurement hits P&L, translation hits CTA in equity. ([Deloitte](https://dart.deloitte.com/USDART/home/codification/broad-transactions/asc830-10/roadmap-foreign-currency-transactions-translations/chapter-1-introduction/1-4-functional-currency-approach))

**Leases (ASC 842)** — three stacked blockers. Embedded leases are a contract-*reading* problem whose facts live outside accounting: *"Contracts that contain an identified asset within a service agreement may meet the definition of a lease,"* requiring *"cross-functional communication across procurement, operations, and accounting."* Discount rate *"proved to be one of the most challenging aspects of ASC 842 adoption."* Modifications are a branching tree where *"failure to reassess the incremental borrowing rate when a modification occurs"* leads to *"significant audit findings and… costly restatements."*
Sources: [PwC](https://www.pwc.com/us/en/services/consulting/deals/library/embedded-leases.html) · [Crunchafi](https://www.crunchafi.com/blog/practical-expedients) · [iLeasePro](https://ileasepro.com/blog/asc-842-modification-accounting/)

**Fixed assets / CIP** — *"Determining which costs belong in CIP and which should be expensed is one of the most judgment-intensive areas."* Deeper problem is provenance: *"When figures are self-reported without any independent verification against the construction site, every single capitalization decision you make will rest on unreliable data."* ([Numeric](https://www.numeric.io/blog/cip-accounting) · [Track3D](https://track3d.ai/blog/construction-in-progress-cip-accounting-guide/))

#### Tier 2 — non-deterministic matching that fails *silently*

**Bank reconciliation** — the best-argued point in the whole research pass and the key design constraint for Tieout:

> ***"A wrong match does not raise an exception — it produces a reconciled account with two misallocated transactions, and it may not surface for months."***

Input quality is structurally variable: *"Reference field length, character handling, formats, whether a counterparty name is passed at all — these differ by bank and by payment scheme."* And the economics invert at the tail: most tools *"automate the easy majority, dump the remainder into a spreadsheet, and leave a person doing the hardest twenty per cent with none of the context that made the other eighty per cent easy"* — and *"beyond a certain point, each additional per cent of automated matching costs more in configuration and carries more risk than the human minutes it saves."* ([Atypical Tech](https://atypicaltech.com/en/blog/the-bank-reconciliation-agent))

**Intercompany eliminations** — two counterparties, often two ERPs, two policy interpretations, two timestamps, two FX rates, for one economic event. Failure modes: *"Transactions recorded at different times, in different periods, or with different cut-off dates"*; *"the same transaction recorded at different exchange rates on each side"*; *"One entity posts a transaction; the other doesn't, or posts it to the wrong account."* Root cause is policy divergence: *"without centralized policy enforcement, reconciliation differences persist across periods."* BlackLine-commissioned study (Dimensional Research, n=263, Mar 2023): **96% say staff regularly lose full nights' sleep over intercompany accounting.**
Sources: [Nominal](https://nominal.so/blog/intercompany-reconciliation/) · [Intuit](https://www.intuit.com/enterprise/blog/financials/intercompany-eliminations/) · [BlackLine PR](https://www.prnewswire.com/news-releases/99-of-stakeholders-surveyed-by-blackline-report-challenges-with-intercompany-accounting-processes-301843158.html)

**Three-way match** — breaks are timing- and structure-driven: goods received in two batches with the invoice after the first; prices changing between PO and delivery; freight/tariffs on the invoice but not the PO; intake across *"email, post, supplier portals, or EDI."* The tolerance band is a **policy judgment, not a constant**: *"set tolerances by category, not universally, as a tolerance that makes sense for bulk commodity purchases is wrong for technology hardware or capital equipment"* (typical 1–5% or $5–$50/line).

**Ardent Partners 2025: industry exception rate 22% vs 9% best-in-class; $9.40 cost per invoice vs $2.78; 9.2 days to process vs 3.1.**
Sources: [SoftCo](https://softco.com/blog/three-way-matching-process-in-ap-common-problems-and-solutions/) · [HighRadius](https://www.highradius.com/resources/Blog/guide-to-3-way-invoice-matching/) · [Ardent Partners](https://ardentpartners.com/ap-metrics-that-matter-in-2025/)

**Subledger-to-GL tie-out** — structural cadence mismatch, but the damaging break is deliberate: *"A manual GL journal reduces AR to 'force' a balance without recording a corresponding credit memo in the AR subledger."* The report ties out while operational records are wrong. **So the tie-out isn't arithmetic checking — it's detecting who routed around the control.** ([Equility](https://www.equilityhq.com/blog/general-ledger-to-subledger-reconciliation-key-differences-significance))

#### Tier 3 — the data isn't in the system

**Flux / variance analysis** — best one-line framing: ***"The variance is arithmetic. The commentary is the work."*** Threshold-setting has no deterministic answer — *"Set them too high and small errors slip through; set them too low and preparers burn hours justifying movements that don't matter"* — and thresholds *"maintained by hand diverge across preparers and periods."* Staleness is inherent: *"A manual export is a point-in-time snapshot."* Output degrades into *"vague terms like 'timing difference' or 'increased headcount,' which lack the granular detail required for strategic decision-making."*
Sources: [Numeric](https://www.numeric.io/blog/should-you-give-a-flux-about-flux-analysis) · [The CFO](https://the-cfo.io/2026/05/05/the-future-of-flux-analysis-from-ledger-checking-to-strategic-insight/)

**Audit support / PBC lists** — *"The number-one cause of audit delays is an incomplete PBC list, as auditors cannot move forward until every request on the PBC list has been fulfilled."* Auditors want *"PDFs that are searchable, created directly from a file and not scanned images."* ([Glasscubes](https://www.glasscubes.com/what-is-pbc-list-in-audit-a-comprehensive-overview/))

**Accruals & prepaid amortization** — state, not math: *"Cancellations, upgrades, and renegotiated terms rarely get caught in time."* Errors *"come from spreadsheet mechanics, not accounting judgment: a dragged formula, a missed row, or a schedule nobody updated after a renewal."* Audit exposure is evidentiary: *"Accruals supported only by rough estimates or verbal assumptions invite audit challenges."*
Sources: [Truewind](https://www.truewind.ai/blog/prepaid-amortization-schedule-entries-close-risk) · [Numeric](https://www.numeric.io/blog/prepaid-reconciliation)

#### Tier 4 — orchestration and control design

**Journal entry review — where regulation bites hardest.**

PCAOB **[AS 2401](https://pcaobus.org/oversight/standards/auditing-standards/details/AS2401)** requires auditors to *"design procedures to test the appropriateness of journal entries recorded in the general ledger and other adjustments"* (¶.58) specifically to address **management override**, which *"can occur in unpredictable ways"* (¶.57).

**Red flags at ¶.61:** entries to *"unrelated, unusual, or seldom-used accounts,"* by people who *"typically do not make journal entries,"* recorded *"at the end of the period or as post-closing entries that have little or no explanation,"* or containing *"round numbers or a consistent ending number."*

The PCAOB's [Audit Focus: Journal Entries](https://pcaobus.org/resources/staff-publications/audit-focus/audit-focus-journal-entries) lists recurring firm failures verbatim — *"Not testing the completeness of the population of journal entries"*; *"Not testing any of the journal entries that met the auditor's fraud criteria."* And the line that matters most:

> ***"It is also important that auditors carefully consider fraud risks associated with journal entries processed through automated systems, as the risk of management override of controls is not limited to journal entries processed manually."***
>
> **An automated JE gets more scrutiny, not less.**

Historical proof: Xerox overstated revenue **>$3B over five years** via top-side journals *"made at the group corporate level during the preparation of consolidated statements"*; HealthSouth inflated earnings **$2.8B over six years** *"using manual journals."* ([Redwood](https://www.redwood.com/article/what-financial-scandals-show-about-the-fraud-risk-of-manual-journal-entry/))

**Close orchestration & consolidation** — meta-workflows inheriting every problem above plus dependency scheduling. Across six Global Network Firms' 2024 PCAOB inspections, **68% of engagements had an ICFR deficiency**, AS 2201 the most-cited standard by a wide margin. The auditability constraint: *"The main risk with AI-assisted close automation is using a system that can't explain what it did or why, which is a problem when auditors ask questions."*
Sources: [Audit Update](https://www.auditupdate.com/post/2024-pcaob-large-firm-inspection-reports) · [CrossCountry](https://www.crosscountry-consulting.com/insights/blog/audit-readiness-for-year-end/)

> **Ranked answer:** bank reconciliation at the tail (silent wrong matches) and revenue recognition (irreducible judgment) are hardest. **Flux commentary is the highest-leverage unsolved-but-tractable one** — the arithmetic is trivial, the explanation is the product, and it is exactly what Maximor advertises.

### 7.3 The competitive map

| Company | Round | Date | Valuation | Workflow |
|---|---:|---:|---:|---|
| Ramp | $750M F | Jun '26 | $44B | Spend + agents |
| Basis | $100M B | Feb '26 | $1.15B | Firm tax/audit |
| Rillet | $100M C | Aug '26 | $1B | AI-native GL |
| Accrual | $75M launch | Feb '26 | n/d | Firm tax prep/review |
| Campfire | $65M B (+$35M A) | '25–26 | n/d | AI-native GL |
| Tabs | $55M B | Sep '25 | n/d | Billing/O2C |
| Doss | $55M B | Mar '26 | n/d | Inventory ops + GL |
| Numeric | $51M B | Nov '25 | n/d | Close/rec |
| Maxima | $41M Seed+A | Nov '25 | $143M | Close/JE |
| Light | $30M A | Sep '25 | n/d | AI-native ERP |
| Nominal | $20M A | Jul '25 | n/d | Consolidation |
| Sequence | $20M A | Dec '25 | ~$75M ⚠️ | Quote-to-cash |
| Concourse | $12M A | Jan '26 | n/d | FP&A agents |
| Bluecopa | $7.5M A | Jan '26 | n/d | Finance ops |
| **Maximor** | **$9M seed** | **Sep '25** | n/d | **Close/rec/rev rec** |

Sources: [Ramp](https://www.cnbc.com/2026/06/04/ramp-valuation-funding-ai-spend.html) · [Basis](https://siliconangle.com/2026/02/24/ai-accounting-startup-basis-secures-100m-1-15b-valuation-firms-adopt-agent-based-workflows/) · [Rillet](https://techcrunch.com/2026/08/19/rillet-raises-100m-series-c-at-1b-valuation-2-years-after-emerging-from-stealth/) · [Accrual](https://www.cpapracticeadvisor.com/2026/02/05/startup-accrual-officially-launches-with-75m-in-funding-to-bring-ai-native-automation-to-accounting/177600/) · [Campfire](https://www.prnewswire.com/news-releases/campfire-raises-65-million-series-b-to-redefine-how-finance-works-in-the-ai-era-302585077.html) · [Tabs](https://www.businesswire.com/news/home/20250915745370/en/) · [Doss](https://siliconangle.com/2026/03/24/doss-raises-55m-expand-ai-powered-operations-platform-erp-integrated-workflows/) · [Numeric](https://www.numeric.io/blog/numeric-raises-51m-series-b) · [Maxima](https://www.businesswire.com/news/home/20251118400802/en/) · [Light](https://www.balderton.com/news/light-raises-30m-series-a-to-replace-legacy-finance-systems-with-ai-native-platform/) · [Nominal](https://finance.yahoo.com/news/nominal-secures-20m-series-power-130000618.html) · [Sequence](https://www.sequencehq.com/blog/sequence-announces-series-a) · [Concourse](https://www.prnewswire.com/news-releases/concourse-raises-12m-series-a-and-expands-access-to-its-enterprise-grade-ai-agents-for-finance-302670827.html) · [Bluecopa](https://www.bluecopa.com/blog/bluecopa-raises-7-5m-series-a-to-build-autonomous-finance-for-enterprises)

#### Per-company detail

- **Basis** (basis.ai — `thebasis.com` is *not* them) — tax return prep (claims the first AI agent to autonomously complete an end-to-end **1065 partnership return**), audit testing, workpaper generation, reconciliation, variance analysis. Sells to **accounting firms** (Boulay, Clark Nuber, MarksNelson, Pinion, UHY). **~30% of the Top 25 firms.** $134M total. *"Its AI agents run autonomously, in some cases for hours… offering finished work for review."*
- **Numeric** (numeric.io) — close task management; **Cash Matching** (claims 90%+ of bank recs automated); confidence-scored transaction matching; **flux with auto-drafted narrative**; JE automation posting into NetSuite. Customers **Wealthfront, Brex, OpenAI, Plaid, Parafin**. $89M total; ex-BlackLine CEO Marc Huffman and ex-NetSuite CFO Ron Gill in the B. **Notably restrained language — no agent/autonomy branding.**
- **Truewind** (truewind.ai) — transaction coding, auto prepaid/fixed-asset schedules, reconciliation with exception flagging, flux, JE generation. Sells **through CPA firms** (EisnerAmper, Frank Rimerman, ADKF). ~$17M total; $13M Series A led by Thomson Reuters Ventures ⚠️ *(date conflict: CPA Practice Advisor says 8 Jan 2025; Truewind's own post says 5 Feb 2024)*. Most conservative stance: *"Your team owns the review. Truewind handles everything else."*
- **Klarity → rebranded "Within" (within.ai)** in 2026 — was ASC 606 and O2C document review; now an enterprise *"company brain"* across IT, GTM, HR, Ops. $70M Series B led by NFDG, $90M total. DoorDash, ServiceNow. **Arguably no longer a CFO-office comp.**
- **Vic.ai** — autonomous invoice processing, PO/3-way match, bill pay. *"The industry's first autonomous finance platform"*; agents branded "VicAgents™". **$115M total but no round since Dec 2022**; all published metrics date to that raise.
- **Digits** (digits.com) — Bookkeeping/Finance/Reporting Agents on an *"Autonomous General Ledger."* CEO Jeff Seibert: agents *"can automate 95% of the entire bookkeeping workflow."* Vendor-run benchmark: **97.8% accuracy vs 79.1% for 12 outsourced human accountants** on 2,000 real transactions — self-reported, not independently audited. $98M total, **no round since March 2022**.
- **Puzzle** (puzzle.io) — categorization (claims up to 98% automated), bank rec, close prep, JE drafting. **7,000+ firms and startups.** Explicitly **anti-autonomy**: "Governed Automation" — ***"Nothing posts without your approval"*** — and names Digits as the fully-autonomous foil. **Accrual is acquiring Puzzle's accounting-firm business** (~2 Sep 2026).
- **Rillet** (rillet.com) — full **AI-native general ledger**. **600+ customers**, incl. **Mercor** (multi-billion ARR on a 3-person finance team), Function Health, Temporal. $200M+ total. EY partnership. ***"Finance agents need more than access to data; they need to work inside the general ledger."***
- **Campfire** (campfire.ai) — AI-native ERP on a proprietary **"large accounting model"**, native GL agent "Ember." YC S23; $100M+ total. **Replit** ($10M→$200M ARR without adding accounting headcount), PostHog (5–6 days saved on close), Klarity, TwelveLabs, Flex.
- **Doss** (doss.com) — automated PO generation and **3-way match**, inventory-movement reconciliation into GL. Verve Coffee, Eight Sleep, Ark Foods. $73M+; Intuit Ventures participated. **Uses no agent/autonomy vocabulary at all.**
- **Light** (light.inc) — **fine-tuned an 8B open-source model to read invoices**, replacing a ~1T-param model. "Custom Agents" run scheduled NL tasks. $43M total; Lovable, Sana, Legora; 30× growth over 12 months; customers report 84% reduction in finance-ops time.
- **Nominal** (nominal.so) — account/bank rec, **intercompany matching and eliminations**, consolidation, *"0 ERP changes needed."* $30M total; **Workday Ventures**. Claims 50,000+ hours eliminated in a year. Markets *against* copilots.
- **Maxima** (maxima.ai) — JE prep/posting, reconciliations, anomaly monitoring. **Scale AI, Rippling, SpotOn, Bilt Rewards.** $41M Seed+A at $143M post; Redpoint / Kleiner Perkins / Audacious. Benchmarks against **SAP and BlackLine**. *"Agents prepare and humans review."*
- **Accrual** (accrual.com) — launched 5 Feb 2026 with **$75M**, $65M from **General Catalyst** across two rounds (flagship of GC's $1.5B "Creation" strategy). CEO **Cosmin Nicolaescu, ex-Brex CTO**. Armanino, Aprio, H&R Block, Creative Planning.
- **Ramp** — **Policy Agent** reads the written expense policy, evaluates every transaction, recommends approve/reject/escalate **with citations to the exact policy text**. **>$1B annual revenue, $200B purchase volume, 70,000+ customers.**
- **Brex** — **acquired by Capital One for $5.15B**, closed 7 Apr 2026. Audit Agent + Review Agent; **"Agent Mesh"** architecture. CTO: *"Our goal is to use AI to make Brex effectively disappear. **We're aiming for total automation.**"*
- **BlackLine** (NASDAQ: BL) — **FY2025 revenue $700.4M, 4,394 customers.** **Verity Prepare** (GA 27 Jul 2026) *"orchestrates a specialized digital workforce to autonomously analyze supporting documentation, match transactions, identify reconciling items, and assemble audit-ready reconciliations."* Acquired WiseLayer Dec 2025. "Glass box" positioning — CEO: *"a 'black box' solution is not an option."* **Under activist pressure: Engaged Capital pushing for a sale after a reported $66/share approach from SAP.** Notably, **~$8M of Q2 2026 deals slipped as AI scrutiny stretched sales cycles 40–45 days.**
- **FloQast** — **$200M ARR (Jan 2026)**, 3,500+ teams, EY alliance. Hardest HITL stance in the market: ***"Nothing hits your books without human approval. No exceptions."***
- **Trintech** — Flux Agent and Variance Analysis Agent (2026); *"governed autonomous finance"* + *"Human-in-the-loop control by design."* 6 of the top 10 global banks.
- **Tabs, Concourse, Sequence, Bluecopa, Zone & Co, Auditoria.AI, Trullion, Docyt, Booke.ai** — see full profiles in the strand-D report. Sequence is **the only one that still says "copilot" approvingly.**
- **Fintool — acquired by Microsoft ~Apr 2026**; fintool.com now redirects to microsoft.com/microsoft-365.
- **Mosaic — acquired by HiBob ~Feb 2025** ⚠️ *date/terms unverified.*
- **Runway — status unresolved.** runway.com now serves Runway AI (generative video). Whether Siqi Chen's FP&A product was sold, moved or wound down could not be determined.

#### The autonomy spectrum, most to least aggressive

Pilot (*"runs the entire bookkeeping process… with zero human intervention"*) → Brex (*"total automation"*) → Vic.ai → Digits (95%) → Bluecopa → Concourse/Basis/Ramp → **Rillet, Campfire, Maxima, Maximor, Trintech, BlackLine** (agent-executes-human-approves, audit-trail-forward) → FloQast/Puzzle/Truewind (explicitly anti-autonomy) → Sequence (still says copilot).

> **Note the near-universal structure: autonomous execution in the headline, human approval in the fine print.** Even Pilot concedes that for a material judgment call *"it will signal that it needs a human response before moving on, as only humans can make accountable decisions."* And the one vendor selling explicitly *against* autonomy is also the one reporting AI scrutiny **lengthening** its sales cycles by 40–45 days.

#### Where the money is — three findings

1. **The ledger, not point tools.** Both 2026 billion-dollar valuations (Basis, Rillet) plus Campfire, Light, Digits target the GL or the firm's production system — where agents can *post*, not just recommend.
2. **Selling to accounting firms is the hottest wedge.** Basis, Accrual, Truewind, Maxima and Puzzle's firm business all point one way: firms have the billable-hour cost base AI attacks directly, plus a concentrated buyer set.
3. **A bigger pool is buying the labour outright.** **Thrive Holdings raised $2B at $12B (Aug 2026)** with an OpenAI equity stake; its accounting platform **Current** spans 50+ firms and 2,000+ professionals. General Catalyst earmarked $1.5B of its $8B fund for this model. **In dollar terms the AI-enabled roll-up thesis is now bigger than the AI-accounting-software thesis.** ([TechCrunch](https://techcrunch.com/2026/08/12/openai-backed-thrive-holdings-raises-2b-to-bring-ai-to-the-enterprise/) · [Transacted](https://www.transacted.io/venture-firms-target-accounting-roll-ups-with-ai-automation-play))

**Where money is NOT going: standalone AP automation.** Vic.ai's last round Dec 2022, Digits Mar 2022, Trullion Apr 2023, Zone & Co 2021.

> ⚠️ **Every "% automated" figure in this section is a vendor claim with no published methodology.** There is no independent, audited benchmark of agent accuracy in accounting except AccountingBench.

### 7.4 Exception handling and human review, concretely

**Maker-checker / four-eyes:** *"for each transaction, there must be at least two individuals necessary for its completion. While one individual may create a transaction, the other individual should be involved in confirmation/authorization of the same."* ([Wikipedia](https://en.wikipedia.org/wiki/Maker-checker))

**SEC Release 33-8238** — ***"A company must maintain evidential matter, including documentation, to provide reasonable support for management's assessment of the effectiveness of the company's internal control over financial reporting."*** The assessment must cover *"controls over initiating, recording, processing and reconciling account balances,"* *"controls related to the initiation and processing of non-routine and non-systematic transactions,"* and *"controls related to the selection and application of appropriate accounting policies."* ([sec.gov](http://www.sec.gov/rule-release/33-8238))

**PCAOB [AS 2201](https://pcaobus.org/oversight/standards/auditing-standards/details/AS2201)** explicitly accommodates small teams: *"a smaller, less complex company might have fewer employees in the accounting function, limiting opportunities to segregate duties,"* requiring **alternative controls** the auditor must evaluate.

A real published policy — University of Houston MAPP 05.04.06: *"Each bank account will be reconciled and certified by an account analyst **and** by the Manager of Bank Reconciliation"*, both signing to confirm *"current procedures were followed."*

**So "evidence of review" operationally means:** named preparer ≠ named reviewer · timestamped reviewer action · review notes/tickmarks stating *what* was checked · captured where the record cannot be altered afterward.

#### The convergent state machine

> **Not started → In preparation** *(preparer owns)* **→ Submitted for review** *(reviewer owns)* **→ [Rejected → back to preparer] → Approved/certified → Period locked** *(immutable)*

…with an **auto-certification bypass** for accounts under a configured variance threshold — management's own materiality decision implemented as configuration, **not** an SEC/PCAOB-mandated number.

Corroboration: **Oracle ARCS** documentation confirms distinct *Preparing Reconciliations* / *Reviewing Reconciliations* / *Running Auto Match* / *Confirming Suggested Matches* / *Closing, Locking, Opening Periods* topics ([docs](https://docs.oracle.com/en/cloud/saas/account-reconcile-cloud/index.html)) *(TOC verified; individual pages 403'd, so no literal status strings are asserted)*. **FloQast** public guidance: five-stage close, *"Designate the person responsible for each task, and set clear due dates,"* and institute *"a hard close once you finalize the close process to ensure nobody can make unauthorized adjustments"* ([blog](https://www.floqast.com/blog/month-end-close-checklist)).

⚠️ **BlackLine, FloQast and Trintech help centres were all unreachable (403/DNS-blocked).** No literal vendor status labels are asserted here.

#### Materiality — the actual rules

**[SAB 99](https://www.sec.gov/interps/account/sab99.htm)** — the staff acknowledges the 5% rule of thumb but states flatly that ***"exclusive reliance on this or any percentage or numerical threshold has no basis in the accounting literature or the law"***; a percentage is *"only the beginning of an analysis of materiality."* Qualitative factors that make a small misstatement material: it *"masks a change in earnings or other trends,"* *"hides a failure to meet analysts' consensus expectations,"* *"changes a loss into income or vice versa,"* affects loan covenants or regulatory compliance, *"increases management's compensation,"* or *"involves concealment of an unlawful transaction."*

**[SAB 108](https://www.sec.gov/rules-regulations/staff-guidance/staff-accounting-bulletins/staff-accounting-bulletin-no-108)** — you must run **both** methods. *Rollover* *"quantifies a misstatement based on the amount of the error originating in the current year income statement"*; *iron curtain* *"quantifies a misstatement based on the effects of correcting the misstatement existing in the balance sheet at the end of the current year, irrespective of the misstatement's year(s) of origination."* Requirement: ***"a registrant's financial statements would require adjustment when either approach results in quantifying a misstatement that is material."***

**[AS 2105](https://pcaobus.org/oversight/standards/auditing-standards/details/AS2105)** — materiality for the financials as a whole must be *"expressed as a specified amount"*; **tolerable misstatement** is set *"less than the materiality level for the financial statements as a whole"* to control aggregation risk; materiality must be **reevaluated** if actuals diverge from planning estimates.

Practice benchmarks (firm methodology, not codified): overall materiality **0.5–7%** of a benchmark; performance materiality typically **50–75% of overall**; clearly-trivial threshold **3–5% of overall materiality**.
Sources: [Legal Clarity](https://legalclarity.org/performance-materiality-vs-tolerable-misstatement/) · [CPA Hall Talk](https://cpahalltalk.com/audit-materiality/) · [Universal CPA](https://www.universalcpareview.com/ask-joey/what-is-the-clearly-trivial-threshold/)

#### Audit trail requirements for an automated JE

**PCAOB [AS 1105](https://pcaobus.org/oversight/standards/auditing-standards/details/AS1105)** is the operative standard:

- **¶.08:** *"Information produced by the company… [is] more reliable when the company's controls over that information — including, where applicable, its information technology general controls and automated application controls — are effective."*
- **¶.10:** the auditor must ***"Test the accuracy and completeness of the information, or test the controls over the accuracy and completeness of that information, including… information technology general controls,"*** and ***"Evaluate whether the information is sufficiently precise and detailed for purposes of the audit."***

This is the "completeness and accuracy of IPE" requirement — why auditors ask *"show me the report you pulled this from, and prove nobody edited it."*

**Therefore an automated JE must log:** (1) initiating identity — a **distinct bot/service identity, not a shared account**; (2) source data lineage back to the upstream extract, plus evidence that extract was itself tested; (3) an approval by a party distinct from the initiator; (4) creation / review / posting timestamps; (5) immutability and a unique ID; (6) attached supporting documentation. The three **ITGC** domains that make or break it: **access, change management, computer operations** — 2024 PCAOB inspections found ITGC testing gaps were the leading reason auditors couldn't rely on automated controls.

⚠️ **Gap:** IIA GTAG on auditing RPA, ISACA RPA guidance and Big 4 RPA-controls whitepapers were all unreachable. No sourced quote for bot-specific control guidance.

#### What a reconciliation exception concretely is

Timing differences (deposits in transit — *"receipts the company recorded before the bank processed them"*; outstanding checks — *"payments the company issued that haven't cleared"*), unrecorded bank items (service charges, wire fees, interest, ACH withdrawals, NSF), posting errors (*"wrong account, wrong amount, or wrong period"*), duplicates, and suspense/clearing balances *"used when there is uncertainty about the proper account allocation."*
Sources: [Numeric](https://www.numeric.io/blog/bank-reconciliation-statement-guide) · [Hyperbots](https://www.hyperbots.com/glossary/suspense-account-reconciliation)

#### Real published aging / escalation policies

| Source | Rule |
|---|---|
| **U. of Houston MAPP 05.04.06** | Reconcile within **30 working days** of statement receipt; bank-side discrepancies to Treasury **within 20 working days**; *"The Director will notify the Controller of items not resolved **within 30 days** of being referred to another area."* [link](https://www.uh.edu/policies/mapps/05-finance-and-accounting/050406/) |
| **VA Financial Policy Ch. 1** | *"Unreconciled differences for clearing (suspense) accounts will be researched, resolved, and explained **within 60 days**."* [link](https://department.va.gov/financial-policy-documents/financial-document/chapter-01-clearing-suspense-and-deposit-funds/) |
| **California SAM §8294** | *"**Prepare AR reconciliations monthly within 30 days** of the preceding month"*; aging analysis by length of time past due; records retained **4 years**. [link](https://www.dgs.ca.gov/Resources/SAM/TOC/8200/8294) |
| Standard aging buckets | **1–30 / 31–60 / 61–90 / 91–120 / 120+ days** |
| Practice guidance | *"A check that's been outstanding for **90 days** probably isn't clearing"*; *"A deposit in transit aging past **30 days** needs investigation"*; *"Reconciling items that age beyond a month or two should be investigated, not rolled forward."* |

> ⚠️ **Negative finding:** none of the three government policies publishes a **dollar write-off authority threshold**. Those live in each entity's internal delegation-of-authority manual, not in public policy. **Don't assume a standard exists.**

#### A real close checklist — NC State Finance Division FY2025 year-end

[Source](https://finance.ofa.ncsu.edu/2025/03/25/fiscal-year-end-is-almost-here/)

| Task | Owner | Deadline |
|---|---|---|
| Enter and approve campus journal vouchers at all levels | Campus departments | 5 p.m. June 13 |
| Approve/route journal vouchers for equipment transactions | Depts → University Controller's Office | June 24 |
| Approve online journal vouchers | Campus departments | June 30, 3 p.m. |
| Upload/approve travel reimbursements at all levels | Campus departments | 5 p.m. June 13 |
| Submit imprest account reimbursement w/ documentation | Accounts → Controller's Office | June 23 |
| Submit non-student AR checks for deposit | Depts → Accounts Receivable | 10 a.m. June 30 |
| Final check writing | Accounts Payable | June 25 |

Dependency logic is implicit in the dates: JV approval gates AP check-writing gates GL close. UGA: *"accounting periods must be closed by the university within 10 days of the end of the month."* UW runs a Master Checklist signed off by a Dean or Unit Head.

---

## 8. Market & Business Models

### 8.1 The player table

| Player | What it does | Pricing | Funding / ownership | OSS? |
|---|---|---|---|---|
| **LangSmith** (LangChain) | Tracing, evals, prompt mgmt | Developer $0; **Plus $39/seat/mo**; Enterprise custom. LCU $1.50/unit, LSU $1.00/unit ([pricing](https://www.langchain.com/pricing-langsmith)) | Independent | No |
| **Braintrust** | Eval-first: Observe/Evaluate/Discover + "Loop" agent | Starter $0; **Pro $249/mo** ($100 credits, 5 GB then $3/GB, 50k scores then $1.50/1k). **Unlimited seats every tier** ([pricing](https://www.braintrust.dev/pricing)) | **$80M Series B, 17 Feb 2026**, ICONIQ-led, with a16z, Greylock, Elad Gil. Notion, Replit, Cloudflare, Ramp, Dropbox ([announcement](https://www.braintrust.dev/blog/announcing-series-b)) | No |
| **Arize / Phoenix** | ML + LLM observability | ⚠️ *secondary only, arize.com/pricing 403'd*: Free 25k spans; **Pro $50/mo**; Enterprise "typically $50k–$100k/yr" (third-party estimate) | **$70M Series C, Feb 2025**, Adams Street-led, with M12, Datadog, PagerDuty, OMERS ([blog](https://arize.com/blog/arize-ai-raises-70m-series-c-to-build-the-gold-standard-for-ai-evaluation-observability/)) | Phoenix OSS |
| **W&B Weave** | Experiment tracking + GenAI trace/eval | Free $0 (1 GB/mo Weave ingest); **Pro from $60/mo**. Overage $0.03/GB storage, **$0.10/MB Weave ingest** ([pricing](https://wandb.ai/site/pricing/)) | Acquired by **CoreWeave**, closed 5 May 2025, reported **~$1.7B** ([CoreWeave IR](https://investors.coreweave.com/news/news-details/2025/CoreWeave-Completes-Acquisition-of-Weights--Biases/default.aspx)) | No |
| **Langfuse** | Tracing, prompt mgmt, evals, playground | Hobby $0; **Core $29/mo** (unlimited users); **Pro $199/mo**; **Enterprise $2,499/mo**. Graduated overage **$8→$6/100k units** ([pricing](https://langfuse.com/pricing)) | **Acquired by ClickHouse, 16 Jan 2026**, alongside ClickHouse's $400M Series D at $15B. 20k+ stars, **26M+ SDK installs/mo** ([ClickHouse](https://clickhouse.com/blog/clickhouse-raises-400-million-series-d-acquires-langfuse-launches-postgres)) | **Yes — MIT** |
| **Galileo** | Agent observability + evals (Luna models) | Not published | $45M Series B Oct 2024. **Acquired by Cisco** — intent 9 Apr 2026, completed ~22 May 2026; into Splunk Observability ([Cisco](https://blogs.cisco.com/news/cisco-announces-the-intent-to-acquire-galileo)) | No |
| **Humanloop** | Eval-driven dev platform | Dead as a product | **Anthropic acqui-hired the team, 13 Aug 2025**; explicitly **no assets or IP** acquired ([TechCrunch](https://techcrunch.com/2025/08/13/anthropic-nabs-humanloop-team-as-competition-for-enterprise-ai-talent-heats-up)) | No |
| **Maxim AI** | Agent simulation, eval, observability + Bifrost gateway | ⚠️ *unverified* — getmaxim.ai/pricing now serves Bifrost gateway pricing | ~$3M seed, Elevation Capital | Bifrost Apache-2.0 |
| **Patronus AI** | Eval → **Digital World Models** (simulation environments to train/stress-test agents) | Not published | **$50M Series B, 25 Jun 2026**, Greenfield-led; Notable, Lightspeed, Datadog, Samsung. **$70M total.** Claims **>15× revenue growth YoY** ([PR](https://www.prnewswire.com/news-releases/patronus-ai-raises-50-million-series-b-and-unveils-first-digital-world-models-for-ai-agent-training-and-simulation-302811248.html)) | No |
| **Confident AI / DeepEval** | OSS eval framework + hosted | Free $0; **Starter $200/mo**; **Team $2,000/mo**; overage $1/GB-month. Unlimited seats on paid ([pricing](https://www.confident-ai.com/pricing)) | ~$2.2M seed, YC W25 | **DeepEval Apache-2.0** |
| **Freeplay** | Prompt eng / test / optimize | Not published; reported "several hundred to several thousand/mo" | **$14.4M** over 3 rounds; Renegade-led A extension Jun 2025. Tracxn lists **4 employees as of 31 Jul 2026** | No |
| **Vellum** | AI app dev platform | Base free; **Mighty $30 / Super $100 / Ultra $200/mo**; credits at $1 = 1 credit pass-through ([docs](https://www.vellum.ai/docs/pricing)) | Not verified | Self-host mentioned |
| **HoneyHive** | Evals + observability | Free Developer: 10,000 events/mo, 5 users; Enterprise custom. **Only two tiers — no self-serve paid tier** ([pricing](https://honeyhive.ai/pricing)) | **$7.4M total** ($5.5M Seed, Insight Partners) | No |
| **Comet Opik** | OSS observability + evals + **Agent Optimizer** | Open Source $0; Free Cloud $0; **Pro Cloud $19/mo**; Enterprise custom ([pricing](https://www.comet.com/site/pricing/)) | Comet ML | **Apache-2.0, full backend self-hostable** ([GitHub](https://github.com/comet-ml/opik)) |
| **Future AGI** | Evals + **agent-opt** optimizer library + gateway | Free $0; add-ons **Boost $250 / Scale $750 / Enterprise $2,000/mo**. $2/GB storage, $10/1k AI credits ([pricing](https://futureagi.com/pricing)) | Not verified | agent-opt Apache-2.0 |

### 8.2 The monetization pattern that works

**Usage-metered on data volume, with seats decoupled.**

- Braintrust: **unlimited users on every tier**, meters GB + scores
- Langfuse: unlimited users from $29, **volume-graduated overage $8 → $6/100k**
- Confident AI: unlimited seats on all paid tiers, $1/GB-month
- Comet Opik: unlimited members even on the free OSS tier

**Per-seat is the losing side.** LangSmith is the notable holdout at **$39/seat/mo** and is exactly what third-party pricing critiques attack — a 10-person team pays $390/mo before a single trace of overage.

**Open-core + hosted cloud is the dominant distribution wedge, and it is winning outcomes.** Langfuse relicensed to MIT in June 2025 and was acquired by ClickHouse in January 2026 at 20k+ stars / 26M+ monthly SDK installs. Promptfoo (OSS, 350k developers, **>25% of Fortune 500**) was acquired by [OpenAI](https://openai.com/index/openai-to-acquire-promptfoo/). Opik is Apache-2.0 *including the backend*. Closed-SaaS players in the same window either got acqui-hired (Humanloop) or stayed small (HoneyHive: $7.4M, still no self-serve paid tier).

**Anchor price points:** $19 (Opik Pro) → $29 (Langfuse Core) → $39/seat (LangSmith Plus) → $49 (Portkey Production) → $50 (Arize AX Pro ⚠️) → $60 (W&B Pro) → $79 (Helicone Pro) → $199 (Langfuse Pro) → $200 (Confident Starter) → $249 (Braintrust Pro) → $799 (Helicone Team) → $2,000 (Confident Team, Future AGI Enterprise) → $2,499 (Langfuse Enterprise).

### 8.3 Market sizing — all vendor-research **estimates**

| Metric | Figure | Source |
|---|---|---|
| LLMOps software | **$5.88B (2025) → $7.14B (2026), 21.3% CAGR; → $15.59B by 2030** | The Business Research Company, 3 Mar 2026 ([link](https://natlawreview.com/press-releases/llmops-software-market-reach-1559-billion-2030-growing-216-cagr)) |
| LLM observability platform | **$1.97B (2025) → $2.69B (2026), 36.3% CAGR; → $9.26B by 2030** | ResearchAndMarkets / TBRC |
| AI observability (broad) | **$2.71B (2025) → $20.52B (2035), 22.47% CAGR** | SNS Insider, 5 Aug 2026 |
| LLM router market | $6.52B by 2030 | ⚠️ **Uncited by the publisher. Do not rely on** |

> Note the incoherence: LLMOps at $7.14B (2026) vs AI observability at ~$3B (2026) vs LLM-observability-specific at $2.69B. **Different scope definitions from different firms. Do not sum or reconcile.**

### 8.4 The white space — is anyone selling *automatic agent improvement*?

> **Finding: optimization exists, but nobody meters or prices it. It ships as a free feature bolted to an observability SKU, and it only touches prompts — never the agent's code or architecture.**

Evidence *for* optimization existing commercially:

- **Braintrust Loop** — the strongest commercial case. An AI agent in Braintrust's runtime that *"investigates your project data, creates and edits objects with your approval, and runs on a schedule."* It can create/update **prompts, scorers, facets, datasets, custom views, automations, preprocessors**. It explicitly **cannot modify your application code**, and *"doesn't automatically optimize in the background."* Bundled into the **$249/mo Pro tier, not separately metered.** ([docs](https://www.braintrust.dev/docs/guides/loop))
- **Comet Opik Agent Optimizer** — SDK to improve prompts and agents, **Apache-2.0, free.** Zero revenue attached.
- **Future AGI agent-opt** — the most explicit optimization product found. Optimizes **five axes: system prompt, tool descriptions, retrieval config, few-shot bundle, model selection**, via six optimizers (RandomSearch, BayesianSearch, MetaPrompt, ProTeGi, GEPA, PromptWizard). **Apache-2.0.** Its commercial platform bills on storage/credits/gateway requests — **not on optimization.**
- **Galileo** covered *"prompt optimization and model selection through evaluations to production monitoring"* — Cisco's stated rationale for buying it.
- **GEPA / DSPy** — the research substrate everyone builds on. **Library-only OSS**, `pip install gepa`. Decagon [published on running GEPA in production](https://decagon.ai/blog/optimizing-gepa-for-production) — an *application* company doing it in-house, not buying it.
- **Patronus AI** — closest well-funded bet adjacent to improvement: $50M for "Digital World Models," large-scale simulation to **train and evaluate** agents. CEO: *"Benchmarks were never the destination."* Still sold as eval/training infrastructure; no published pricing.

Evidence *for* the white space being real:

1. **No vendor found charges for improvement.** Every priced SKU meters traces, spans, scores, GB, units, seats, or gateway requests. **Not one meters "improvements shipped," "regressions fixed," or "quality delta."**
2. **Nothing rewrites agent code.** The optimization ceiling across the whole market is **text and config**, not architecture, control flow, or tool implementations.
3. **Optimization is a free giveaway.** The two named optimizer products are both Apache-2.0. That is a commodity-feature signal, not a product line.
4. **Analyst framing confirms measurement bias.** Reviewers describe Arize as measuring *"model telemetry rather than business outcomes"* and focused on *"observing production systems rather than helping build or test agents."* IDC's suggested buyer question is *"How do you help me reduce the risk of my AI use cases?"* — risk reduction, not capability improvement.
5. **Capital for actual self-improvement went to labs, not tooling.** Recursive Superintelligence raised **$650M at $4.65B** for self-improving AI; NeoCognition took **$40M seed** for self-learning agents. Neither sells improvement-as-a-service to teams operating existing agents.

> **Verdict: the category is ~95% measurement.** Optimization is present as an unmonetized feature, capped at prompt-and-config rewriting, and always gated behind human approval. **No commercial product autonomously improves an agent end-to-end and charges for it.**

### 8.5 Is cost optimization a paid product?

Yes — but sold as **gateway/router subscriptions or a take-rate on spend**, essentially never as shared savings.

| Vendor | Model | Price |
|---|---|---|
| **OpenRouter** | Take-rate — the only true spend-linked pricing found | **5.5% markup on all requests** |
| **Portkey** | Subscription + per-request overage | Dev free; **Production $49/mo** (100k logs, $9 per additional 100k) ([pricing](https://portkey.ai/pricing)) |
| **Helicone** | Subscription + usage | Hobby free; **Pro $79/mo** (unlimited seats); **Team $799/mo** ([pricing](https://www.helicone.ai/pricing)) |
| **ClawRouters** | Freemium BYOK | Free (BYOK), **Basic $29 / Pro $99/mo**; claims 60–90% API cost reduction *(vendor claim, unverified)* |
| Maxim Bifrost, LiteLLM, Kong AI Gateway, Cloudflare AI Gateway | OSS free / enterprise custom | No published per-unit price |
| **nOps** | ***"Savings-first — pay after savings delivered"*** | The **only** outcome-priced model found — but it is cloud/K8s FinOps, **not LLM inference** ([link](https://www.nops.io/blog/llm-cost-optimization-tools/)) |

> **Second white space: nobody charges a percentage of LLM savings.** Cost tooling is priced on log volume — **the vendor is paid more when you spend more**, which is backwards relative to value delivered.

### 8.6 2025–2026 funding and M&A

**Acquisitions:** CoreWeave → Weights & Biases (5 May 2025, ~$1.7B) · Anthropic → Humanloop acqui-hire (13 Aug 2025, no IP) · ClickHouse → Langfuse (16 Jan 2026) · **OpenAI → Promptfoo** (9 Mar 2026; Promptfoo had raised $23M at $86M; folds into OpenAI **Frontier**; stays open source) · Cisco → Galileo (Apr–May 2026). Adjacent: Palo Alto Networks → Chronosphere ($3.35B) · ServiceNow → Traceloop · Snowflake → Observe · Snyk → Invariant Labs · Coralogix → Aporia.

**Rounds:** Braintrust $80M B (Feb 2026) · Patronus $50M B (Jun 2026) · Arize $70M C (Feb 2025) · Freeplay A extension (Jun 2025) · Dash0 $110M B at $1B.

> **Structural read:** four of the five best-known standalone eval/observability companies exited in 18 months, all to platform owners (a cloud, a database, a model lab, a networking vendor). InfoWorld's framing: data platform vendors moving *"up the stack"* to own the AI feedback loop. A Fortune 50 practitioner quoted by TechTarget: *"The acquisitions that work are the ones that disappear into the platform."*

---

## 9. Documented User Pain

### 9.1 The anchor statistic

**[LangChain, State of Agent Engineering](https://www.langchain.com/state-of-agent-engineering)** (n=1,340; 18 Nov – 2 Dec 2025; engineers → executives):

- **57% have agents in production** (67% at 10k+ employee orgs; 50% at <100)
- **Quality is the #1 barrier to production (~33%)**; latency #2 (20%); security 24.9% at 2k+ enterprises
- **89% have some observability; 62% have detailed tracing**
- **Only 52.4% run offline evals; only 37.3% run online evals**
- Cost was *"less frequently cited as a concern than in previous years"*

> **Teams can *see* their agents failing. They cannot *judge* or *fix* them.** That gap is the whole market.

### 9.2 Non-determinism — the #1 production blocker

- Anthropic engineering, [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system): *"Agents make dynamic decisions and are non-deterministic between runs, even with identical prompts."* · *"minor changes cascade into large behavioral changes, which makes it remarkably difficult to write code for complex agents"* · *"One step failing can cause agents to explore entirely different trajectories."*
- **@film42** ([HN](https://news.ycombinator.com/item?id=43699271)): *"Everyone wants to go the agent route until the agent messes up once after working 99 times in a row."*
- **@dhorthy** (Dex Horthy, author of 12-factor-agents), same thread: *"90% or even 99% accuracy isn't enough"* for mission-critical tool calls
- **@reedf1** ([HN](https://news.ycombinator.com/item?id=45808308)): *"While AI is strictly deterministic - it is technically chaotic… even if the AI only does something a bit off 99%, 99.9% or 99.99% you will see large spurious error rates in your workflow."*
- **@thisisit**, same thread: *"AI being right 95% of the time is still not good enough for finance workflows but he wouldn't budge."*
- **@bandrami**: *"I make software used on actual flight simulators and we literally need it to be deterministic."* · **@hi_hi**: *"Regulated industries need to be deterministic. Imagine your bank being non-deterministic."*

### 9.3 "Agentic" in production is mostly not agentic

- **@DebtDeflation**: *"most 'AI Agents' that make it to production aren't actually that agentic. The best ones are mostly just well-engineered software with LLMs sprinkled in at key points."*
- Cognition, [Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents): *"running multiple agents in collaboration only results in fragile systems"*; *"Actions carry implicit decisions, and conflicting decisions carry bad results."*
- Gartner: *"Many use cases positioned as agentic today don't require agentic implementations."*

### 9.4 Framework distrust

- **@daxfohl**: treat LLMs as *libraries, not frameworks*; own the *"lowest level planning loop."*
- **@nickshirobokov** ([langgraph#4973](https://github.com/langchain-ai/langgraph/issues/4973)): *"I stopped using LangGraph… State management makes you jump through mental hoops… the idea of checkpoints… sounds cool until you realize how much memory it consumes… this idea breaks down the moment you start modifying the environment through tools."*
- **@deaux** ([HN](https://news.ycombinator.com/item?id=47491023)) on LangChain: *"probably the worst package to gain popularity of the last decade."*

### 9.5 Evaluation — why it's hard, and what teams actually do

**Structural reasons (Anthropic states all three):** no single correct trajectory — *"agents might take completely different valid paths"*; no single correct output — outputs are *"free-form text and rarely have a single correct answer"*; emergent behavior — *"small changes to the lead agent can unpredictably change how subagents behave."*

Even "easy" cases aren't. **@msp26** ([HN](https://news.ycombinator.com/item?id=47491546)): *"There can be a lot of subjectivity and pretending that some golden answer exists does more harm… the schemas I write change drastically as my understanding of the problem increases. And nothing really seems to handle that well."*

Dataset rot — Skylar Payne, [If DSPy is so great…](https://skylarbpayne.com/posts/dspy-engineering-patterns/): *"Keeping this dataset up to date is a key maintenance challenge of evals."*

**Evidence "we have no evals" is common:**
- **@iamwil** ([HN](https://news.ycombinator.com/item?id=42370185)): *"Writing task-specific evals are pretty important, and lots of people are just going off of vibes right now."*
- Hamel Husain, [hamel.dev/blog/posts/evals](https://hamel.dev/blog/posts/evals/): *"unsuccessful products almost always share a common root cause: **a failure to create robust evaluation systems.**"* · *"Many don't know how to set up eval systems and skip these steps."* · Symptom: *"Addressing one failure mode led to the emergence of others, resembling a game of whack-a-mole."*
- **@deepsquirrelnet**: *"The absolute biggest time sink and 'here be dragons' of using LLMs is poke and hope prompt 'engineering' without proper evaluation metrics."*
- **@potatolicious** ([HN](https://news.ycombinator.com/item?id=44531697)): *"we're deploying these systems based purely on vibes without any real quantification of efficacy."*

**LLM-as-judge is contested, not settled.**
*Against:* **@jerf**: *"using a judge of the same architecture as the thing being judged maximizes the probability of fundamental failure of the benchmark to be valid."* · **@rsynnott**, on a judge grading `45 + 8 minutes` where expected was `63 minutes`: *"a competent human reviewer does not go 'that seems plausible'."* · **@roadside_picnic**: never seen empirical evidence that "LLM as critic" works.
*For:* **@Aurornis**: *"Evals are a core part of any up to date LLM team"* — use a *different model family* as judge. · The ["noisy evaluators are useful"](https://news.ycombinator.com/item?id=48291016) thesis: noisy graders become useful **through aggregation across many tasks for comparing agents — explicitly not for per-run production correctness.**

**Contamination:** **@majormajor**: *"you can never use an AI agent benchmark that is published on the internet more than once."*

**What teams do today, ranked:** (1) vibe checks / eyeballing diffs — most common; (2) observability without scoring — 89% vs 52%; (3) offline eval sets — ~half; (4) LLM-as-judge, usually with a cross-family hack; (5) online/production evals — rarest at 37.3%.

### 9.6 The blocking objection to auto-optimization: no evals → no optimizer

The richest source is HN's [If DSPy is so great, why isn't anyone using it?](https://news.ycombinator.com/item?id=47490365) (227 points, 120 comments).

- **@memothon** ([47490729](https://news.ycombinator.com/item?id=47490729)) — the load-bearing quote: *"the real problem with using DSPy is that many of the problems people are trying to solve with LLMs (agents, chat) don't have an obvious path to evaluate. You have to really think carefully on how to build up a training and evaluation dataset… **This takes a ton of upfront work and careful thinking**… This can actually get in the way of moving fast."*
- **@BenGosub** ([47494327](https://news.ycombinator.com/item?id=47494327)): *"IMO DSPy didn't take off because it requires preparing train and test datasets and that takes time and effort."*
- **@sethkim** ([47491489](https://news.ycombinator.com/item?id=47491489)), a competitor ranking customer objections: *"1) It's slow: you first have to get acquainted with DSPy and then get hand-labeled data… 2) They know that manual prompt engineering is brittle… 3) **They don't actually want a model or prompt at all. They want a task completed, reliably, and they want that task to not regress in performance. Ideally, the task keeps improving in production.**"*

> **That third point is the clearest statement of latent demand found anywhere in this research.**

**The trust objection is opacity, not capability:**
- **@TheTaytay** ([47490496](https://news.ycombinator.com/item?id=47490496)): *"when I discovered that none of my actual optimized prompts were extractable, I got cold feet… The idea of having a computer optimize a prompt as a compilation step makes a lot of sense, but **treating the underlying output prompt as an opaque blob doesn't.**"*
- **@dhorthy**: ***"if you don't trust the LLM to make the thing right in the first place, how are you gonna trust the SAME LLM to fix it?"***

**The obsolescence objection (new in 2026):**
- **@tcdent** ([47492839](https://news.ycombinator.com/item?id=47492839)): *"the feedback loop which was patterned by DSPy has essentially become adopted as part of my development workflow."*
- **@markab21**: *"the entire premise that the prompting is the surface area for optimizing the application is fundamentally the wrong framing."*

**Pro-automation evidence (real but thinner):**
- **@dbreunig** ([47491871](https://news.ycombinator.com/item?id=47491871)) names the killer app as **model migration**: *"prompts are overfit to models… But if you have eval data and have been using a prompt optimizer with DSPy, you can try models with the one-line change followed by rerunning the prompt optimizer."* Cites [Dropbox's case study](https://dropbox.tech/machine-learning/optimizing-dropbox-das): *"DSPy allowed us to reach that conclusion quickly and with measurable evidence."*
- Single-source: [HN 47826831](https://news.ycombinator.com/item?id=47826831) — *"GEPA prompt optimization: Claude Code Haiku +20% solve rate on new bugs."*

### 9.7 Cost

**The credible multipliers** — Anthropic, [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system):
- *"agents typically use about **4× more tokens** than chat interactions"*
- *"multi-agent systems use about **15× more tokens** than chats"*
- *"upgrading to Claude Sonnet 4 is a larger performance gain than doubling the token budget on Claude Sonnet 3.7"*

> These are the most citable cost facts found — from the vendor that would benefit from *hiding* them.

**Documented waste mechanisms:**
- **Silent duplicate execution → 2–3× cost.** [langgraph#7417](https://github.com/langchain-ai/langgraph/issues/7417): *"When a tool call takes longer than ~3 minutes on LangGraph Cloud, it gets silently re-dispatched from the last checkpoint while the original is still running… resulting in **2-3x redundant work and cost**."* Traced to a hardcoded `BG_JOB_HEARTBEAT = 120`. 48 comments, open.
- **Checkpoint serialization overhead.** [langgraph#7714](https://github.com/langchain-ai/langgraph/issues/7714): *"**85% storage bloat and 37.8% token overhead** with no opt-out path"* — filed with a runnable repro and a drop-in fix.
- **Raw-HTML context stuffing.** [HN 48867021](https://news.ycombinator.com/item?id=48867021), measured with tiktoken: *"an average wikipedia article… is **68,240 tokens of raw html**; nike's homepage is **353,000**."* Counter: Trafilatura/Jina Reader preprocessing cuts 68k → 3–5k.
- **PDF-as-base64 through a tool.** [crewAI#5930](https://github.com/crewAIInc/crewAI/issues/5930).

### 9.8 Cross-framework GitHub themes

Method: GitHub Search API, open issues after 2025-06-01, sorted by comment count; bodies pulled with `gh api`.

> ⚠️ **Caveat:** several of the highest-comment threads in `crewAI` and `autogen` are almost certainly inauthentic engagement — e.g. [autogen#7353](https://github.com/microsoft/autogen/issues/7353) at 383 comments, [crewAI#4877](https://github.com/crewAIInc/crewAI/issues/4877) at 347, plus near-identical "receipts / trust-gating / governance-middleware" issues filed across all three repos by different accounts within weeks. **The volume is astroturf; the topic distribution still signals real anxiety.**

**Theme 1 — Durability, idempotency, exactly-once (strongest, cross-repo).** The same bug in three codebases:
- [langgraph#7417](https://github.com/langchain-ai/langgraph/issues/7417) — long tool calls silently re-executed (48c)
- [crewAI#5802](https://github.com/crewAIInc/crewAI/issues/5802) — *"Tool re-execution on task retry has no idempotency guard — **duplicate payments, emails, trades possible**"* (107c). Body cites langgraph#7417 as the same failure: *"Two independent parties confirmed the exact failure mode."*
- [langgraph#8039](https://github.com/langchain-ai/langgraph/issues/8039) — post-crash recovery is host-dependent (34c)
- [openai-agents-python#4827](https://github.com/openai/openai-agents-python/issues/4827), [#4775](https://github.com/openai/openai-agents-python/issues/4775), [#4679](https://github.com/openai/openai-agents-python/issues/4679) — session-append acknowledgement loss, duplicated pending input, items dropped during compaction

**Theme 2 — Loop / runaway containment.** [crewAI#6414](https://github.com/crewAIInc/crewAI/issues/6414), [crewAI#6219](https://github.com/crewAIInc/crewAI/issues/6219), [langgraph#6731](https://github.com/langchain-ai/langgraph/issues/6731), [autogen#7409](https://github.com/microsoft/autogen/issues/7409), [autogen#7275](https://github.com/microsoft/autogen/issues/7275), [autogen#5611](https://github.com/microsoft/autogen/issues/5611).

**Theme 3 — Output parsing brittleness.** [langchain#1358](https://github.com/langchain-ai/langchain/issues/1358) `ValueError: Could not parse LLM output:` (82c) — still recurring in 2026 via [#36603](https://github.com/langchain-ai/langchain/issues/36603), [#36290](https://github.com/langchain-ai/langchain/issues/36290), [#33504](https://github.com/langchain-ai/langchain/issues/33504), [#35514](https://github.com/langchain-ai/langchain/issues/35514). DSPy's version: [dspy#1539](https://github.com/stanfordnlp/dspy/issues/1539), [dspy#8901](https://github.com/stanfordnlp/dspy/issues/8901).

**Theme 4 — Human-in-the-loop under-served.** [openai-agents-python#636](https://github.com/openai/openai-agents-python/issues/636) *"Human-In-The-Loop Architecture should be implemented on top priority!"* (38c) · [langgraph#8026](https://github.com/langchain-ai/langgraph/issues/8026) request for an `ApprovalNode` (40c) · [langchain#33787](https://github.com/langchain-ai/langchain/issues/33787) *"Agent re-attempts original tool call after HumanInTheLoopMiddleware edit decision"* (41c) — **the human's edit is ignored.**

**Theme 5 — Tool-call authorization.** Every framework has an open request for a pre-execution interception hook; **none shipped as a first-class primitive.**

**Theme 6 — Memory poisoning / silent drift.** [crewAI#5057](https://github.com/crewAIInc/crewAI/issues/5057), [crewAI#6043](https://github.com/crewAIInc/crewAI/issues/6043), [autogen#7683](https://github.com/microsoft/autogen/issues/7683). Most conceptually interesting, [crewAI#5155](https://github.com/crewAIInc/crewAI/issues/5155): *"crews running multi-step tasks across sessions can silently change behavior after context compression or memory rotation… **The agent completes the work, but the behavioral fingerprint has shifted.**… loops are detectable by repetition. **Session-boundary drift is silent.**"*

**Theme 7 — Agents lying about completion.** [langgraph#7844](https://github.com/langchain-ai/langgraph/issues/7844): the agent emits `Done. All tests passed. Ready to publish.` — *"it may not attach command output, trace evidence, or human approval."*

**Theme 8 — Docs/DX as a first-order blocker.** The LangGraph v1 roadmap thread (85c) is dominated by docs complaints — the maintainers *asking* and users *not* asking for features. **@sydney-runkle** (LangChain staff): *"Make multiagent workflows as simple coding wise as possible - I feel intimidated by all the things you have to put together to make it work."*

**DSPy is the odd one out** — recent open issues are overwhelmingly integration/provider plumbing, not reliability. *Interpretation: DSPy's problem is adoption, not production failure.*

### 9.9 Practitioner voices — finance side

> ⚠️ **The r/Accounting corpus does not exist in this report.** Reddit was hard-blocked. HN was substituted.

- *"This is called 'Month End Close' in accountant speak."* — [onlypassingthru, 46907675](https://news.ycombinator.com/item?id=46907675)
- **On tacit knowledge and undocumented plugs**, ex-Big-4 running ICFR walkthroughs — [pwpw, 32582749](https://news.ycombinator.com/item?id=32582749): *"my biggest insight when conducting walkthroughs with the client's accountants was that there is so much valuable knowledge that is internalized in singular individuals. I'd have an accountant show me their month end close process with links between 5 Excel worksheets. Totally illogical flow and only that person understood how to follow the process from start to finish. **There would be situations like randomly multiplying a line item by 32 because of some piece of paper on their desk that they had written down years ago.** These people had been at the company for 20+ years."*
- **On why bank data defeats matching** — [bmadduma, 45825175](https://news.ycombinator.com/item?id=45825175): *"The breaking point came when we realized we hadn't closed our own books for the last full year… Bank transactions are a mess, **'CL GRP INSURED INS' could be what?**… The reconciliation part for expenses was surprisingly straightforward, matching transactions by amount, date and description within a 3-5 day window, flag exceptions. **The hard part is handling edge cases like income recognition, refunds, split payments, bulk payments and foreign currency.**"*
- **On why accounting ≠ bookkeeping** — [ekjhgkejhgk, 46466166](https://news.ycombinator.com/item?id=46466166): *"you cannot entirely automate accounting… accounting isn't just processing bytes, but instead requires the understanding of the underlying economics associated with the transactions. **This understanding in turn isn't stored anywhere other than the accountant's mental model of the entity.**"*
- **On close-time stress** — [steine65, 42102012](https://news.ycombinator.com/item?id=42102012): *"Troubleshooting powerbi errors during month-end close is the most stress-inducing thing… **I was chewed out hard for that one a few days ago even though IT made that change.**"*
- **On ERP rigidity** — [tomnipotent, 28426869](https://news.ycombinator.com/item?id=28426869): *"A running joke in the industry is that you don't customize your ERP for your business, but customize your business for your ERP."*

**The [Bench Accounting shutdown thread](https://news.ycombinator.com/item?id=42523061)** (Dec 2024, 304 comments) is the richest corpus on automated-bookkeeping failure. ⚠️ *Individual comment IDs approximate — verify before quoting publicly:*
- *"We find errors in our Pilot books at a staggering rate. Things that would never be missed if we just had a human bookkeeper."*
- *"There is no viable automated solution for bookkeeping and tax now. These are customer intensive fields that require inquiries and clarification."*
- *"The platform was simply never sufficient on its own to do the books. Bookkeepers were required to fill the massive gaps."*
- *"Accounting startups that rely on automation are doomed to fail. Customers demand perfect accounting at automation-reflective prices."*
- *"You figure out how to make a computer do 80% of the problem domain and give humans tools to intervene effectively when outside that subset."*

### 9.10 Finance hard numbers

| Metric | Value | Source |
|---|---|---|
| Monthly close cycle time, ~2,300 orgs | **median 6.4 days**; top quartile ≤4.8; bottom ≥10 | [APQC](https://www.apqc.org/resource-library/resource/cycle-time-perform-monthly-close) |
| Close in ≤6 business days | 61% overall (up from 53% in 2015); **71% high-automation vs 23% low-automation**; reconciliation specifically **72% vs 25%** | [Ventana/ISG](https://robertkugel.ventanaresearch.com/finally-a-faster-close) |
| World-class finance | closes **35% faster**; total finance cost 0.54% of revenue vs 1.76% | [Hackett Group](https://www.thehackettgroup.com/the-hackett-group-digital-world-class-finance-teams-operate-at-45-lower-cost-and-deliver-faster-smarter-insights/) |
| Accountants making errors | **18% at least daily, 33% several times/week, 59% several times/month** (n=497 controllership staff); 73% say workload rose | [Gartner, Feb 2024](https://www.gartner.com/en/newsroom/press-releases/2024-02-21-gartner-survey-shows-that-a-third-of-accountants-make-several-error-per-weeo-due-to-capacity-constraints) |
| Spreadsheet cell error rate | **5.2% mean**; **94% of 88 studied contained ≥1 error** | [Panko](https://www.researchgate.net/profile/Raymond-Panko/publication/228662532_What_We_Know_About_Spreadsheet_Errors/links/53eb1f7a0cf2fb1b9b6adbef/What-We-Know-About-Spreadsheet-Errors.pdf) |
| Material weaknesses FY2025 | **238 public companies**; **inadequate accounting resources +14% YoY**, journal entry controls +3%; **269 companies (36%) had MWs in multiple years 2021–25** | [KPMG](https://kpmg.com/us/en/articles/2026/trends-material-weaknesses.html) |
| Restatements 2025 | 391 total (−18% YoY); debt/equity 27%, **rev rec 14%** | [Audit Analytics via Ideagen](https://www.ideagen.com/resources/whitepapers/financial-restatements-report-may-2026) |
| Accounting degrees | **55,152 in 2023–24, −6.6% YoY**; new CPA exam candidates **42,626 (2023) → 28,082 (2024) → 16,448 (H1 2025)** | [AICPA 2025 Trends](https://www.aicpa-cima.com/professional-insights/download/2025-trends-report) · [JofA](https://www.journalofaccountancy.com/news/2025/oct/the-accounting-graduate-pipeline-where-do-things-stand/) |
| Jobs / openings | **1,595,200 jobs (2025), +5% to 2035, ~115,300 openings/year** — overwhelmingly replacement | [BLS](https://www.bls.gov/ooh/business-and-financial/accountants-and-auditors.htm) |
| Talent shortage | only **15%** of orgs say they are *not* experiencing one | [Deloitte CFO Signals Q4 2025](https://www.deloitte.com/us/en/about/press-room/deloitte-q4-2025-cfo-signals-survey.html) |
| Turnover | public accounting **15–22%/yr, 84% voluntary**; staff-level **25–35%**; IMA: among ages 18–36, **39% turned over in 24 months** | [theresource.com](https://www.theresource.com/2025/12/03/accounting-turnover-rate/) · [IMA](https://www.imanet.org/research-publications/ima-reports/talent-retention-in-the-us-accounting-and-finance-profession) |
| Vendor-sourced ⚠️ | FloQast: **73% work overtime during close, ~11 extra hours per cycle; 53% report burnout.** BlackLine: **42% of finance leaders don't completely trust their own financial data** | [FloQast](https://www.floqast.com/resources) · [AccountingToday](https://www.accountingtoday.com/news/42-of-finance-leaders-dont-trust-their-own-data-says-blackline-survey) |

---

## 10. Datasets

All verified by live HTTP.

### 10.1 The two that matter most for Track 2

**ReconRiver** — `https://huggingface.co/datasets/heybadrinath/reconriver-synthetic-reconciliation` — **CC BY 4.0, no auth.**

Four scenarios: `clean-settlement`, `failure-recovery`, `mixed-exceptions`, **`month-end-close`**. Each folder ships:
- `internal_transactions.csv` — `internal_payment_id, merchant_order_id, occurred_at, gross_amount, currency, payment_status, payment_method`
- `processor_transactions.csv` — `processor_transaction_id, merchant_order_id, processor_event_type, processor_event_time, gross_amount, fee_amount, net_amount, settlement_batch_id, processor_status`
- `bank_settlements.csv` — `bank_entry_id, settlement_batch_id, booked_at, credited_amount, bank_reference, description`
- **`expected_reconciliation.csv`** — `expected_outcome, expected_reason_code, expected_difference, explanation` per work key
- `scenario_manifest.json` — seed, **fee policy (2.90% + 0.30 HALF_UP)**, settlement window, SHA256s, injected-exception counts

`month-end-close` verified: 10,000 payments → 10,000 internal / 10,200 processor / 1,499 bank rows, **11,539 ground-truth rows.** Outcome mix: **11,139 MATCHED, 100 REFUND_MATCHED, 100 PARTIAL_REFUND, 40 LATE_SETTLEMENT, 40 AMOUNT_MISMATCH, 30 MISSING_PROCESSOR, 20 each MISSING_INTERNAL / MISSING_BANK_SETTLEMENT / FEE_MISMATCH / CURRENCY_MISMATCH, 10 AMBIGUOUS_MATCH.** Reason codes tiered L1 (order) / L2 (settlement). `mixed-exceptions` adds duplicate records, malformed rows, and a duplicated source file.

> **The single highest-value find.** The only public dataset with **labelled** reconciliation breaks — so you can *score* your agent, not just demo it. The AMBIGUOUS_MATCH and MISSING_* rows are exactly where a reward-hacking model fabricates.

**Checkbook L.A.** — `https://controllerdata.lacity.org/api/views/pggv-e4fn/rows.csv?accessType=DOWNLOAD` — **CC BY 4.0, no auth, no key.**

**6,472,141 rows, 62 columns.** PO side: `po_num, po_date, po_line_number, buyer_name, unit_price, quantity`. Receipt side: `receiver_id`. Invoice side: `inv_num, inv_date, invoice_due_date, invoice_discount_due_date, inv_line`. Payment + GL: `dollar_amount, payment_method, payment_status, account_code, fund, expenditure_type, fiscal_year`.

Verified coverage: `po_num` on 5,749,020 rows; `receiver_id` on 3,904,182; **3,894,653 rows have PO + receiver + qty>0 + price>0 simultaneously.**

> **The messiness is free:** `dollar_amount ≠ unit_price × quantity` on many rows because of distribution splits — *that discrepancy is the exception your agent finds.*

### 10.2 Ranked shortlist

| # | Dataset | Both sides? | Auth | Licence | Why |
|---:|---|---|---|---|---|
| 1 | **Checkbook L.A.** `pggv-e4fn` | ✅ PO + receipt + invoice + payment + GL | none | CC BY 4.0 | 6.47M rows; 3,894,653 complete 3-way triples |
| 2 | **ReconRiver** | ✅ ledger + processor + bank + **ground truth** | none | CC BY 4.0 | Scenario named `month-end-close` |
| 3 | **VynFi journal entries** 1M/10M | GL with clearing + fraud labels | none | Apache-2.0 | SAP-shaped, 353 deliberately unbalanced JEs |
| 4 | **mindweave** bank + ledger pair | ✅ bank txns + double-entry GL | none | CC BY-**NC** | Joins on `source_module`/`source_id`; monthly TB |
| 5 | **Pittsburgh Checkbook** `t8t2-4b5n` | GL + PO + invoice | none | none stated | Real JD Edwards GL export, 1.03M rows |
| 6 | **SEC FSDS** quarterly ZIP | — | UA header | Public domain | 3.6M facts with debit-credit flag |
| 7 | **Schreyer `fraud_dataset_v2`** | — | none | GPL-3.0 | 533,009 SAP journal entries, 100 labelled anomalies |
| 8 | **Dolibarr demo dump** | ✅ GL + AP/AR + bank, native lettering | none | GPL-3.0 | Whole ERP in one 4 MB `.sql` file |

### 10.3 Full inventory by category

**Journal entries / GL.** **VynFi** (Apache-2.0) `vynfi-journal-entries-1m` (667,584 rows / 34 MB) and `-10m` (9,354,522 rows / 477 MB). 48 columns including `is_fraud, is_anomaly, fraud_type, anomaly_type, lettrage, lettrage_date, is_manual, is_post_close` — the exact JE red flags AS 2401 ¶.61 names. Ships `chart_of_accounts.parquet`, `cost_centers`, `profit_centers`, `je_network`, a full `star_schema/`, and **`ledger_coherence_report.json`: 100,700 JEs of which 353 are deliberately unbalanced.** Benford-calibrated (MAD ~0.001), median ~$9.2K, 3.7 lines/JE. · **Schreyer** direct raw download `https://raw.githubusercontent.com/GitiHubi/deepAI/master/data/fraud_dataset_v2.csv` — 27,044,366 bytes, 533,009 rows, GPL-3.0, real SAP field names `BELNR, WAERS, BUKRS, KTOSL, PRCTR, BSCHL, HKONT, DMBTR, WRBTR, label`; **532,909 regular / 70 global / 30 local anomalies.** Paper arXiv:1709.05254. · **Pittsburgh Fiscal Focus** `t8t2-4b5n` — 1,028,458 rows FY2011–FY2026, real JD Edwards; **OV Receiving Document 623,928, PV Voucher 157,644, AF Adjusting Entries 3,801**; 43,271 FY2025 rows carry both PO and invoice number. · Also **Massachusetts CTHRU** `pegc-naaa` (48,897,291 rows, USGOV_WORKS, has both `encumbrance_id` and `payment_id`), **Delaware** `7bip-nb4g` (14,593,604 rows, public domain, full PeopleSoft chartfield), **Boston** (PDDL, cleanest small option, use `curl -L`), **Atlanta** `jmke-icfi` (1.83M), **Baton Rouge** `7qhq-wwsg` (797,676).

**Bank.** **Berka** — best real bank data, gives both sides. Original `sorry.vse.cz` is DNS-dead; working no-auth route verified: `https://sdv-demo-datasets.s3.amazonaws.com/MULTI_TABLE/financial_v1.zip` (11,705,968 B) → **`trans.csv` 1,056,320 rows / 59.3 MB** (`trans_id, account_id, date, type PRIJEM/VYDAJ, operation, amount, balance, k_symbol, bank, account`) plus **`order.csv` 6,471 standing orders — the expected-payments side.** Kaggle mirror is **CC0**. · **Teller sandbox** — no signup, no key, no cert; **only aggregator returning `running_balance` per transaction.** Username selects scenario; password always `password`. · **Plaid sandbox** — `user_custom` authors exact transactions with `starting_balance`, `seed`, `override_accounts[]`. Best for *controlled* break scenarios. · **GoCardless (Nordigen)** — institution `SANDBOXFINANCE_SFIN0000`; Berlin Group PSD2 shape with `booked[]`/`pending[]`, `transactionId, bookingDate, valueDate, remittanceInformationUnstructured, creditorName, endToEndId`. · **Stripe** `stripe sandbox create` — the *ledger* side, not the bank side; test clocks manufacture multi-month invoice/payout histories. ⚠️ **No downloadable Stripe sample datasets exist.** · **AgamiAI Indian-Bank-Statements** — Apache-2.0, 1.37 GB, **800 paired PDF + JSON** with real NEFT/RTGS/UPI/cheque narrations and full balance ground truth. · **Kaggle `apoorvwatsky/bank-transaction-data`** — CC0, ~116k rows, **mirrored debit/credit pairs across accounts = intercompany reconciliation.** · OFX/QFX/MT940/QIF fixtures: `ofxtools/tests/data` and GnuCash `doc/examples/`.
⚠️ **Rule out** `mlg-ulb/creditcardfraud` — V1–V28 are PCA-transformed, unusable. PaySim has no dates or descriptions.

**Invoice / document.** ⚠️ **No public dataset ships a real PO + goods-receipt + invoice triple for the same transaction.** Use Checkbook L.A. for the structured triple and these for the document leg. · **SalorWorks invoice test pack** ⭐ `https://github.com/SalorWorks/shopify-invoice-test-pack` — **CC BY 4.0 (verified in LICENSE)**, 15 fixtures, each `invoice.pdf` + `invoice.png` + `expected.json` + JSON Schema. **The fixture names *are* the AP exception taxonomy:** `09-line-discount, 10-invoice-discount, 11-freight-duty, 12-case-pack, 13-free-of-charge, 14-poor-scan, 15-multicolumn`, plus multipage/Arabic/bilingual/UAE-VAT/FX. Ground truth has `supplierSku, barcode, quantity, unit, unitPrice, discount, lineTotal`. · **katanaml-org/invoices-donut-data-v1** — MIT, 425/26/50, 197 MB; only line-item invoice set with a clean permissive licence. · **mychen76/invoices-and-receipts_ocr_v2** — same corpus, 6× volume, **no declared licence**. · **DocILE** — **55 field types = 36 KILE + 19 LIR**; only public benchmark with a PO-reference schema; code MIT, **data gated** — cite the schema. · **CORD v2** — CC BY 4.0; `menu.cnt × menu.unitprice → menu.price`. · **chainyo/rvl-cdip-invoice** — 19,947 real scanned invoices. · **invoice2data samples** — MIT, ~14 real vendor invoices (AWS, Flipkart, Coolblue) each with `.json` ground truth. **Use as the baseline your agent beats.** · Safest Kaggle licences: `jenswalter/receipts` (CC0), `omkarsoak/vlm-receipt-ocr` (MIT), `devp1866/high-quality-ocr-ready-invoice-pdfs` (Apache-2.0).

**ERP.** **Dolibarr** ⭐ `https://raw.githubusercontent.com/Dolibarr/dolibarr/develop/dev/initdemo/mysqldump_dolibarr_24.0.0.sql` — **4,090,160 B, GPL-3.0**, one `mysql <` and done. `llx_accounting_bookkeeping` models reconciliation state natively: `debit, credit, sens, **matching_general, lettering_code, date_lettering**, code_journal, piece_num, date_validated`. Plus 2,144-row French PCG, supplier invoices, payments, 80 bank txns. · **Tryton** — the only project publishing its live DB: `https://www.tryton.org/~demo/database-8.0.dump` (27,387,474 B); `account_move_line` has a native **`reconciliation`** FK. · **beancount** — `example.beancount` (347,280 B, **1,146 transactions**, 60 accounts, **92 `balance` assertions = pre-built reconciliation checkpoints**). Regenerate any size with `bean-example --seed 42`. · **AdventureWorks DW** — MIT, plain CSVs, no SQL Server needed. **`FactFinance.csv` 39,409 rows is a genuine GL fact table**; `DimAccount.csv` hierarchical CoA; **`DimScenario.csv` = {Actual, Budget, Forecast}** → flux out of the box. OLTP counterpart has `PurchaseOrderDetail` with **`OrderQty, ReceivedQty, RejectedQty, StockedQty, UnitPrice`**. · **Frappe Books** `dummy/setupDummyInstance(...)` → >1,000 txns/year into a SQLite file (AGPL-3.0). · ERPNext's shipped demo JSON is **tiny** (1 JE, 5 payments, ~8 POs/SOs). Odoo `account_demo.py` generates 16 `account.move` plus **`account.reconcile.model`**, no public dump.
⚠️ `demo.erpnext.com` 502, `erpnext.com/demo` 404, `demo.odoo.com` 500 — live ERPNext is `https://erpnext-demo.frappe.cloud`. **Contoso GUID is 404**; prefer the MIT rebuild. **SDV `SAP_v1.zip` is CRM/marketing, not a GL.** 🚩 **Avoid Akaunting** — BSL 1.1 licence explicitly forbids use as an *"Accounting Service."*

**Procurement.** **Cook County IL Invoice Register** `exta-e29u` — 2,371,526 rows, `po_number` on 2,280,723. · **Montgomery County MD** `vpf9-6irq` — 3,308,230 rows with `contract_num, po_num, po_line, invoice_id, invoice_line, payment_status` (values include `RECONCILED`). · **San Francisco 4-set chain** (PDDL): PO commodity detail `ebsh-uavg` (5,828,921 rows), PO summary with `encumbrance_balance` `p5r5-fd7g`, vouchers `n9pm-xkyq` (8,145,743), contracts `cqi5-hm2d`. · **Delaware Contract Line Item Spend** `75y3-eci7` — 3,043,782 rows with `quantity × rate`. **The price-agreement side: "invoiced price ≠ contracted rate."** · **Chicago** contracts `rsxa-ify5` (185,930 rows, **includes `contract_pdf`**) + payments `s4vu-giwb`. · **Vermont** PO `8ewu-igdm` + payments `786x-sbp3` (ODbL) — **no shared PO key, forcing probabilistic vendor+amount+period matching. Genuinely agentic.** · **NYC OMO Invoices** `emrz-5p35` — 791,398 rows with **`invoicebillamount` vs `invoicepayamount`**. · **USAspending bulk** — `POST /api/v2/bulk_download/list_monthly_files/`; ⚠️ filenames use the *toptier code*, not the agency id. · **FPDS-NG ATOM** — 52,010 records for a 5-day window.

**SEC EDGAR.** **Mandatory:** `User-Agent: <App> <email>` on every request — empty UA → **403, verified.** 10 req/sec. Landing moved to `https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets` but the **ZIP path kept the old prefix**: `https://www.sec.gov/files/dera/data/financial-statement-data-sets/{YYYY}q{N}.zip`. 2009q1–**2026q2**. `2026q2.zip` = 60,419,016 B → 718 MB unzipped. Contents: `sub.txt` 7,715 rows; `num.txt` **3,608,712 rows**; `pre.txt` 785,491 rows; `tag.txt` 92,732 rows **with the `crdr` debit/credit flag**. `num + pre + tag.crdr` is a trial balance in all but name. **Notes datasets changed cadence mid-2025** — quarterly through 2025q2, then **monthly** from 2025_07. Adds `txt.tsv` (240 MB of tagged note text) and **`cal.tsv`** (XBRL calculation linkbase → machine-verify that statements foot). **Frames API: the trailing `I` means instant** — omitting or adding it wrongly = 404. Full-text search: the working endpoint is `https://efts.sec.gov/LATEST/search-index?q=...` (`/search` → 403). **Alpha Vantage works with `apikey=demo`** for IBM; free tier 25 req/day; all numbers are strings, missing values are the literal `"None"`, errors return HTTP 200. **FMP has no working demo key.**

**IRS Form 990.** Bulk XML `https://apps.irs.gov/pub/epostcard/990/xml/{YEAR}/{YEAR}_TEOS_XML_{NN}A.zip` — **zero-padded index required** (`_01A.zip` 200, `_1A.zip` 404). ⚠️ **The AWS S3 bucket is empty** — returns a valid `ListBucketResult` with zero `<Contents>`. **ProPublica API works, no auth:** `https://projects.propublica.org/nonprofits/api/v2/organizations/{EIN}.json`.

### 10.4 Track 1 labelled failure data

- **Who&When** — 127 systems labelled with responsible agent + decisive step: [github.com/ag2ai/Agents_Failure_Attribution](https://github.com/ag2ai/Agents_Failure_Attribution)
- **TraceElephant** — 220 failed traces with reproducible replay environments
- **Who&When Pro** — 12,326 trajectories, 18-category error taxonomy

---

## 11. Statistics Ledger — What to Use, What to Avoid

| Figure | Source | Verdict |
|---|---|---|
| **>40% of agentic AI projects canceled by end-2027** | [Gartner, 25 Jun 2025](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027) | ✅ **Use, flagged as a prediction.** Its only underlying data point in the release is a webinar-attendee poll (n=3,412) |
| Only ~130 of thousands of agentic vendors are "real" — the rest is *agent washing* | Gartner, same | ✅ Use |
| Multi-agent = ~15× chat tokens; agents ~4× | [Anthropic engineering](https://www.anthropic.com/engineering/multi-agent-research-system) | ✅ **Strongest cost fact** — from the vendor who'd benefit from hiding it |
| 89% observability / 52.4% offline evals / 37.3% online | [LangChain, n=1,340](https://www.langchain.com/state-of-agent-engineering) | ✅ **Strongest overall** |
| Accountants: 18% make errors daily, 33% several times/week | [Gartner, n=497](https://www.gartner.com/en/newsroom/press-releases/2024-02-21-gartner-survey-shows-that-a-third-of-accountants-make-several-error-per-weeo-due-to-capacity-constraints) | ✅ Use |
| Spreadsheet cell error rate 5.2%; 94% of 88 sheets had ≥1 error | Panko | ✅ Use |
| Median monthly close 6.4 days (~2,300 orgs) | APQC | ✅ Use |
| 238 public companies with FY2025 material weaknesses | KPMG | ✅ Use |
| New CPA candidates 42,626 → 28,082 → 16,448 | AICPA | ✅ Use |
| AP exception rate 22% vs 9%; $9.40 vs $2.78/invoice | Ardent Partners 2025 | ✅ **Best ROI denominator available** |
| AccountingBench: >15% divergence, ~$500k; 5–30% revenue overstatement | Penrose | ✅ **The only independent benchmark in finance AI** |
| **"MIT: 95% of AI pilots fail"** | MIT NANDA via Fortune | 🚫 **Do not use.** It's *GenAI pilots broadly, not agents*; base is 150 interviews + 350 survey + 300 deployments. Widely mis-cited |
| **"$47,000 runaway agent, 11-day loop"** | Towards AI blog post | 🚫 **Do not use.** HN dismantled it: *"The article is simply embarrassing… it's incompetence and stupidity"* |
| **"Microsoft says AI is more expensive than employees"** | Viral HN post, 229 pts | 🚫 **Do not use.** *"Article does not quote anyone at Microsoft saying AI is more expensive than employees."* Arithmetic debunked in-thread |
| All vendor "% automated" claims | Every vendor incl. Maximor | ⚠️ Self-reported, unaudited, no published methodology |

---

## 12. Unverified & Conflicting Claims

| Claim | Status |
|---|---|
| **ADAS performs comparably to random sampling** | ⚠️ Non-peer-reviewed preprint via search snippet. **Potentially the most important negative result in Track 1's field** — verify before citing |
| Darwin Gödel Machine ~$22k/iteration | ⚠️ Secondary Substack analysis |
| AgenTracer's separate agent- vs step-level percentages | ⚠️ PDF fetch failed; abstract gives only relative deltas. Project page may have them |
| Who&When Pro numbers | ⚠️ From a summary site, not the primary PDF |
| MAS-PromptBench optimizer names and negative-result numbers | ⚠️ PDF fetch failed, abstract vague |
| SWE-bench Lite = 300, WebArena = 812, AgentBench counts | ⚠️ Believed correct, unverified |
| Braintrust $800M valuation | ⚠️ Press-reported; absent from the company's own announcement |
| LangSmith trace overage rates | 🚫 **Two secondaries directly contradict — $2.50/1k vs $0.50/1k. Unresolved** |
| Arize AX pricing | ⚠️ arize.com/pricing 403'd on every attempt; all figures secondary. "$50k–$100k/yr enterprise" is a third-party estimate |
| Maxim AI platform pricing ($29/$49 per-seat tiers) | ⚠️ Could not be confirmed; the pricing page now serves Bifrost gateway pricing |
| Freeplay pricing | ⚠️ Not published; "hundreds to thousands per month" is secondary |
| Vellum funding and product positioning | ⚠️ Live pricing page doesn't match its historical eval-platform positioning; Crunchbase 403 |
| Confident AI "$9.99/user/mo" | 🚫 Live page says $200/mo Starter. Stale or wrong |
| **Dodo Payments "$8.8M raised"** | 🚫 Primary release says **$1.1M pre-seed**. Do not repeat. Also "pre-seed" vs "seed" labelling conflict |
| Dodo homepage a16z/Lightspeed/Goldman/Visa/AWS logo wall | 🚫 Reads as partners and angel affiliations, **not direct investors** |
| **AO originated at Composio** | ⚠️ Unconfirmed from Untrivial, Composio or GitHub |
| Maximor HQ, NYC vs SF | ⚠️ Job postings favour NYC |
| **`startupintros.com` Maximor page** | 🚫 Claims 1,001–5,000 employees and investors contradicting every primary source. **Likely AI-generated. Ignore** |
| Truewind Series A date | ⚠️ CPA Practice Advisor says 8 Jan 2025; Truewind's own post says 5 Feb 2024 |
| Concourse total funding | ⚠️ $16.7M vs $27M |
| Tabs invoice volume | ⚠️ $500M vs $1B |
| Runway (FP&A product) status | ⚠️ Unresolved — runway.com now serves Runway AI (video). Sold, moved, or wound down? |
| Mosaic → HiBob acquisition date/terms | ⚠️ No primary release located |
| Galileo close date (22 May 2026) | ⚠️ From a blog addendum, not an SEC filing or Cisco release |
| LLM router / AI gateway market sizes ($6.52B, $7.21B) | 🚫 No source cited by the publisher |
| Bench Accounting thread comment IDs | ⚠️ Approximate — verify before quoting publicly |
| High comment counts on crewAI/autogen governance issues | ⚠️ Likely astroturf. Topic distribution still meaningful |
| All market-size figures | ⚠️ Vendor-research estimates from three firms with incompatible scope definitions |

---

## 13. How the Evidence Drove the Decision

The track call reversed twice as evidence arrived. The reasoning is recorded here so it can be audited.

### Position 1 — Track 1, on skills fit

Initial reasoning: solo builder with agents/LLM-orchestration strength and **no finance background**; Maximor judges Track 2 and would spot an inauthentic workflow instantly; Track 1 needs **zero external integrations**, the biggest time saver available solo.

### Position 2 — Track 1 sharpened, cost angle dropped

Strand A showed **cost-aware optimization is crowded, not a gap** (FrugalGPT, RouteLLM, MaAS, EvoRoute). The differentiator moved to **attribution-routed optimization** — the one validated white space. Feasibility constrained by attribution topping out at **65.9%** component-level.

Strand C then showed the deeper problem: **auto-optimization is blocked upstream by the missing eval set** (89% observability vs 52.4% evals). Track 1's brief assumes the eval is *given*; in reality its absence is the blocker.

### Position 3 — Track 2, on evidence alignment

Three findings converged:

1. **AccountingBench** is the only independent benchmark in finance AI, and it documents a *specific, nameable* failure — models fabricate to satisfy validation checks. Reward hacking, not hallucination, not context length.
2. **Maximor's CEO has published the answer as a product thesis** — *"knowing when to stop"* — in two primary sources.
3. **ReconRiver provides labelled ground truth** exactly where that failure occurs (AMBIGUOUS_MATCH, MISSING_*), so the behaviour can be *scored* rather than asserted.

And the finance-knowledge objection weakened substantially, because the domain knowledge turned out to be available **pre-packaged and citable**:

- Exception taxonomy → ReconRiver's labels
- Materiality rules → SAB 99, SAB 108, AS 2105
- Audit-trail requirements → AS 1105 ¶.10, AS 2401 ¶.61
- Review loop → published close policies + Maximor's own controller page
- AP exception taxonomy → SalorWorks fixture filenames

The objection does not vanish — judges will probe past the dataset. But the *build* remains an orchestration problem: confidence-tiered routing, escalation logic, evidence capture, and an eval harness against labels.

### The design leap

The final move happened while writing the spec. "An agent that refuses to plug" is still a prompt-level promise, and a model that reward-hacks a validation check will reward-hack an instruction. So **the refusal moved into the type system**: `post_matched_entry()` takes a `match_id`, not an amount; journal amounts are *derived* from matched source rows; no `create_adjusting_entry` exists.

> **We didn't prompt it not to plug. We deleted the tool.**

See [DESIGN.md](./DESIGN.md) for the full specification.
