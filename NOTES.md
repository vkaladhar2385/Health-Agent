# NOTES — what to remember after each week

## Week 1 — end-to-end diagnose

- Exit test: inject consumer lag on egress; agent names lag + `max.poll.records` deploy.
- Files: `data.py`, `tools.py`, `graph.py`, `cli.py`.
- Model: personal Anthropic key; `PHA_MODEL=claude-sonnet-5`. Portkey deferred.

## Week 2 — memory + HITL

- Exit test: propose `restart_consumer` → pause → approve → simulated run → incident saved.
- Files: `memory.py`, checkpoint SQLite, interrupt in `graph.py`, `mcp_server.py`.
- Commands: `pha diagnose`, `pha resume`, `pha memory`, `pha-mcp`.
- Interview line: write actions never run without a human decision; decisions are stored.

## Week 3 — evaluation suite (skim)

- Exit test quote: **25/25 scenarios pass** via `uv run pha-eval` / `make eval`.
- Files: `evals/scenarios.py`, `evals/rubric.md`, `evals/runner.py`.
- Interview line: reproducible pass rate, including healthy and escalate negatives.

## Week 4 — observability and guardrails (skim)

- Exit checks: dashboard shows cost/latency per run; prompt-injection test passes (`I01`/`I02`).
- Files to skim:
  - `observability.py` — SQLite traces + `.pha/dashboard.html`
  - `guardrails.py` — per-step tool allow-list, arg validation, max steps/cost
  - `audit.py` — who approved what and when
  - `models.py` — `PHA_PROVIDER=anthropic|openai` adapter
  - `data.py` — `prompt_injection` fault (healthy metrics + malicious log line)
  - `compare_models.py` — `pha-compare` Claude vs OpenAI on a small pack
- Commands: `pha dashboard --open`, `pha audit`, `pha-compare`
- Interview line: “Every write is audited; logs are untrusted data; I can show cost and latency per run without a SaaS lock-in.”

## Week 5 — ship

- Exit test: someone else clones and runs from the README alone.
- Artifacts: `README.md`, `WRITEUP.md`, `DEMO.md`, `.env.example`
- Repo: https://github.com/vkaladhar2385/Health-Agent (make public; push latest)
- You still record the 3-minute video from `DEMO.md`, then add links to resume / LinkedIn.
- Interview line: “Here is a public agent with HITL, evals, audit, and a one-command run path.”
