# Pipeline Health Agent — 5-Week Build Plan

Oct 28, 2026 · @Visu

## Goal and definition of done

Ship a public, working Pipeline Health Agent by Dec 6, 2026. It is the proof for the one Vista requirement I can't meet today: *production agentic systems, including orchestration, tool use, memory, evaluation frameworks, and human-in-the-loop design*.

**Done means all five exist — nothing less counts:**

- [ ] Public GitHub repo with a runnable agent (`docker compose up` or one command)
- [ ] README with an architecture diagram and design decisions
- [ ] Evaluation suite with a pass rate I can quote
- [ ] Tracing dashboard with cost and latency per run
- [ ] 3-minute demo video

A design doc, a plan or a half-built repo is **not** done. Scope: mock TBAR-style pipelines and synthetic data only — no LPL code, data or names.

## Weekly rhythm

About 11–13 hours a week: training on weekdays, building on weekends, and the two feed each other.

| Slot | Time | What |
| --- | --- | --- |
| Mon–Fri | 1 hr/day | Perficient L3 training. End each session by writing one thing to apply to the agent in `NOTES.md`. |
| Sat | 3–4 hrs | Build block 1: the week's main tasks |
| Sun | 2–3 hrs | Build block 2: finish, test, commit, push |
| Sun evening | 15 min | Check-in: did the week's exit criteria pass? |

**Connect the two:** ask Perficient whether the Health Agent can count as your L3 or capstone project. If it can, training hours become build hours. If not, still pick L3 exercises that use LangGraph, MCP or Claude Code on this repo instead of toy examples.

**Rule:** if the week runs short, cut training time, never the build blocks.

## Architecture and tech stack

A LangGraph agent diagnoses faults in simulated pipelines through MCP tools, and any write action waits for a human.

&#91;embedded content: Pipeline Health Agent · agent, tools, memory, guardrails, evals\]

| Layer | Choice | Why |
| --- | --- | --- |
| Orchestration | LangGraph (Python 3.12) | State, checkpoints and interrupts for human-in-the-loop are built in |
| Models | Claude via API, plus one other model behind an adapter | Shows vendor independence; compare both on the evals |
| Tools | MCP Python SDK | The same tools work from the agent, Claude Code and Cursor |
| State and memory | SQLite to start, Postgres optional | Checkpointer plus incident store |
| Observability | Langfuse, self-hosted in Docker | Traces, cost and latency with no vendor account needed |
| Evals and CI | pytest plus GitHub Actions | `make eval` locally, and the same run on every push |
| Packaging | Docker Compose | One command to run, so a reviewer can clone and try it |

Keep AgentCore out of the core. If wanted later, add it as a deployment target behind the same adapter, following the ADOP rule.

## Week-by-week plan

Each week ends with a test I can run, not a feeling of progress. If a week's test fails, the next week starts by fixing it.

### Week 1 (Nov 2–8): skeleton that runs end to end

- [ ] Create public repo `pipeline-health-agent`; Python, `uv` or Poetry, Docker Compose
- [ ] Synthetic data generator: 3 mock pipelines (ingest, stream, egress) with metrics, logs and lag, plus injectable faults
- [ ] Tool 1 `get_pipeline_metrics`, Tool 2 `search_logs`, Tool 3 `get_recent_deploys`
- [ ] LangGraph graph: triage → investigate → diagnose, single model, no memory yet
- [ ] CLI: `pha diagnose --pipeline egress`

**Exit test:** inject a "consumer lag spike" fault; the agent names the cause from the data.

### Week 2 (Nov 9–15): memory, state and human-in-the-loop

- [ ] Checkpointing (SQLite or Postgres) so a run can pause and resume
- [ ] Incident memory: past incidents stored and retrieved as context ("seen this before")
- [ ] Remediation tools: `restart_consumer`, `scale_partitions`, `open_ticket`, all simulated
- [ ] Approval gate: any write action stops and waits for a human approve or reject
- [ ] Expose the tools as an MCP server, so Claude Code or Cursor can call them too

**Exit test:** the agent proposes a restart, pauses, I approve, it runs, and the incident is saved to memory.

### Week 3 (Nov 16–22): evaluation suite

- [ ] 25 golden scenarios: fault injected → expected root cause → expected action
- [ ] Scoring: exact match on action; LLM-as-judge on the diagnosis text with a written rubric
- [ ] Negative cases: no fault (agent must say healthy), ambiguous data (agent must escalate)
- [ ] `make eval` prints pass rate, and CI runs it on every push (GitHub Actions)

**Exit test:** a quoted number, for example "22/25 scenarios pass", reproducible with one command.

### Week 4 (Nov 23–29, Thanksgiving week): observability and guardrails

- [ ] Tracing with Langfuse (self-hosted) or OpenTelemetry: every step, tool call, tokens, cost, latency
- [ ] Guardrails: tool allow-list per step, argument validation, max steps and max cost per run
- [ ] Audit log: who approved what and when (matches the JD's "auditability")
- [ ] Prompt-injection test: a log line containing instructions must not change behaviour
- [ ] Model swap behind an adapter (for example Claude and one other model) and compare eval scores

**Exit test:** a dashboard screenshot showing cost and latency per run; the injection test passes.

### Week 5 (Nov 30–Dec 6): ship it

- [ ] README: problem, architecture diagram, design decisions, eval results, how to run
- [ ] Write-up: "What I learned building a HITL agent for regulated pipelines" (blog or LinkedIn)
- [ ] 3-minute demo video: fault → diagnosis → approval → fix → trace
- [ ] Add the repo link to resume and LinkedIn

**Exit test:** someone else clones the repo and runs it from the README alone.

## How it maps to the Vista JD

Every build item answers a line in the posting, so each one becomes an interview story.

| Vista JD wording | What proves it | Week |
| --- | --- | --- |
| Orchestration, tool use | LangGraph graph with 6 tools | 1–2 |
| Memory | Checkpointing plus incident memory | 2 |
| Human-in-the-loop design | Approval gate on every write action | 2 |
| Hands-on use of Claude Code / Cursor | Tools exposed as an MCP server; repo built with Claude Code | 2 |
| Evaluation frameworks | 25-scenario suite, LLM-as-judge, run in CI | 3 |
| Guardrails, observability | Tracing, cost caps, allow-lists, injection test | 4 |
| Identity, permissions, auditability | Audit log of approvals; per-step tool permissions | 4 |
| Vendor independence | Model adapter plus eval comparison of two models | 4 |
| Reusable reference architectures | README design decisions, written as a reusable pattern | 5 |
| Communicating with executives | Write-up and 3-minute demo | 5 |

## Guardrails against stalling

My usual risk is designing well and not shipping. These rules are there to stop that.

1. **Code before docs.** No new design document until Week 5. Decisions go in short notes in `DECISIONS.md`.
2. **Push every build day.** At least one commit pushed each Saturday and Sunday, even if it's small.
3. **Ugly first.** It has to work before it gets polished. Refactoring waits until the exit test passes.
4. **No scope creep.** New ideas go in `LATER.md`, not into this five weeks.
5. **No new courses or books** until Dec 6, other than Perficient L3.
6. **Missed week = cut scope, keep the date.** Drop a nice-to-have; Dec 6 stays.

**Sunday check-in (15 min):**

- [ ] Did this week's exit test pass?
- [ ] Is the repo pushed?
- [ ] What is the first task next Saturday?

## Application track (in parallel)

Apply this week; the build catches up during the interview process.

- [ ] Decide on the 50% travel before applying
- [ ] Rewrite resume against the 9 qualifications, in order; lead with brownfield and compliance (TBAR) and multi-quarter delivery
- [ ] Use the posting's words: brownfield, compliance, auditability, human-in-the-loop, acceptance criteria for SIs, vendor independence
- [ ] Frame ADOP as a reusable reference architecture with standards, not a pilot
- [ ] Count honestly the time spent hands-on with Claude Code and Cursor; describe depth, not inflated years
- [ ] Submit the application by Nov 1, 2026
- [ ] Prepare 4 stories: TBAR compliance architecture, ADOP framework, working on the SI side, Health Agent (from Week 2 on)
- [ ] Add the repo link to the application or follow-up once Week 3 evals pass
