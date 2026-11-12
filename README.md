# Pipeline Health Agent

A LangGraph agent that diagnoses faults in **mock** data pipelines, pauses on every write/remediation for human approval, remembers incidents, and exposes the same tools over MCP.

Built as a five-week proof for production agentic systems: orchestration, tool use, memory, human-in-the-loop, evaluation, guardrails, and observability.

> Scope: synthetic ingest / stream / egress pipelines only. No customer data.

## Quick start

```powershell
git clone https://github.com/vkaladhar2385/Health-Agent.git
cd Health-Agent
uv sync
copy .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=...
uv run pha diagnose --pipeline egress --decision approve
```

One-command happy path after `.env` is set:

```powershell
uv run pha diagnose --pipeline egress --decision approve
```

## What it does

1. Injects a fault into mock telemetry (metrics, logs, deploys).
2. Runs **triage → investigate → diagnose → propose**.
3. On write actions (`restart_consumer`, `scale_partitions`, `open_ticket` / `escalate`), **pauses for approve/reject**.
4. On approve, runs a **simulated** remediation and stores the incident.
5. Traces latency, tokens, and estimated cost to a local HTML dashboard.

## Architecture

```text
CLI / MCP / pha-eval
        │
        ▼
   LangGraph
   triage → investigate → diagnose → propose
        │
        ├── action none → remember
        └── write action → interrupt (human approve/reject)
                │
                ▼
           remediate (simulated) → remember (SQLite)
        │
        ├── tools: metrics / logs / deploys / memory
        ├── model adapter: Anthropic Claude or OpenAI
        ├── guardrails: allow-lists, max steps/cost
        └── traces + audit log → .pha/dashboard.html
```

| Layer | Choice |
| --- | --- |
| Orchestration | LangGraph (Python 3.12) |
| Runner | `uv` (`uv run pha ...`) |
| Models | Claude by default; OpenAI via `PHA_PROVIDER=openai` |
| Memory / checkpoints | SQLite under `.pha/` |
| Tools | Python functions + MCP server (`pha-mcp`) |
| Evals | 25 golden scenarios (`pha-eval`) |
| Observability | Local trace store + HTML dashboard |

More detail: [TECH_STACK.md](TECH_STACK.md) · command cheat sheet: [COMMANDS.md](COMMANDS.md)

## Design decisions

1. **HITL on every write** — remediation never runs until a human approves. Rejects are stored too. This is the auditability story.
2. **Synthetic data only** — injectable faults, reproducible demos, no regulated production data.
3. **Action policy from telemetry** — `_choose_action` maps metrics/logs to an action; the LLM writes the diagnosis text. Evals score both.
4. **`uv` instead of Docker (for now)** — Docker Desktop on the build machine was org-locked; reviewers can still run with one `uv` command. Compose can return later.
5. **Local dashboard instead of self-hosted Langfuse first** — same Week 4 proof (cost + latency per run) without a container.
6. **Model adapter** — swap Anthropic/OpenAI with env vars; `pha-compare` scores a small pack on both.

## Evaluation results

Golden suite: **25 scenarios** (healthy, lag, errors, schema, hotspot, ambiguous, prompt-injection).

Scoring:

- Exact match on proposed action
- LLM-as-judge on diagnosis text against [evals/rubric.md](src/pipeline_health_agent/evals/rubric.md)

Quoted local run (2026-11-11):

```text
EVAL RESULT: 25/25 scenarios pass
```

Re-run:

```powershell
uv run pha-eval
```

Offline pack checks (no API):

```powershell
uv run pytest
```

CI: [.github/workflows/eval.yml](.github/workflows/eval.yml) (needs `ANTHROPIC_API_KEY` secret).

## Demo path (3 minutes)

```powershell
# 1. Fault → diagnosis → pause
uv run pha diagnose --pipeline egress

# 2. Approve restart
uv run pha resume --thread <thread-id> --decision approve

# 3. Memory + audit + trace
uv run pha memory --pipeline egress
uv run pha audit
uv run pha dashboard --open
```

Prompt-injection check (must stay healthy / action `none`):

```powershell
uv run pha diagnose --pipeline egress --fault prompt_injection
```

Recording outline: [DEMO.md](DEMO.md)

## MCP

```powershell
uv run pha-mcp
```

Point Claude Code or Cursor at that stdio server to call the same tools.

## Project layout

```text
src/pipeline_health_agent/
  data.py           synthetic pipelines + faults
  tools.py          read/write tools
  graph.py          LangGraph workflow + HITL
  memory.py         incident store
  models.py         model adapter
  guardrails.py     allow-lists + budgets
  audit.py          approval audit log
  observability.py  traces + dashboard
  mcp_server.py     MCP entrypoint
  evals/            golden scenarios + runner
```

## Write-up

[WRITEUP.md](WRITEUP.md) — draft for LinkedIn / blog: *What I learned building a HITL agent for regulated pipelines*.

## License / status

Learning / portfolio project. Simulated remediations only.
