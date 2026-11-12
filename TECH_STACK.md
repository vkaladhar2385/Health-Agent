# Pipeline Health Agent — tech stack and why

Stack through Week 4. Matches Vista JD themes: orchestration, tools, memory, HITL, evals, observability, guardrails, vendor independence.

## Current stack

| Layer | Choice | Why |
| --- | --- | --- |
| Language | Python 3.12 | LangGraph + MCP ecosystem |
| Runner | `uv` | One-command local runs; Docker deferred |
| Orchestration | LangGraph | State, checkpoints, interrupts |
| Models | Adapter in `models.py` | `PHA_PROVIDER=anthropic` (Claude) or `openai` (GPT). Swap without rewriting the graph. |
| Default model | `claude-sonnet-5` | Strong diagnose quality |
| Compare model | `gpt-4o-mini` via `pha-compare` | Cheap second vendor for eval comparison |
| Synthetic data | `data.py` | Mock pipelines + injectable faults including `prompt_injection` |
| Tools | Shared Python + MCP | Same read/write tools for CLI and Cursor |
| HITL | LangGraph interrupt | Writes pause for approve/reject |
| Memory | SQLite incidents | “Seen this before” |
| Checkpoints | SQLite | Resume after pause |
| Observability | Local SQLite traces + HTML dashboard | Cost/latency per run without Docker/Langfuse account |
| Guardrails | Allow-lists, arg checks, max steps/cost | Block unsafe tool use and runaway spend |
| Audit | SQLite approvals | Who approved what and when |
| Evals | `pha-eval` | 25 goldens; action match + LLM judge |
| CI | GitHub Actions | Same eval on push |
| Secrets | `.env` | Never commit keys |

## Deferred

| Item | Status |
| --- | --- |
| Docker Compose / self-hosted Langfuse | Deferred (Desktop org lock). Local dashboard covers Week 4 exit. |
| Portkey | Deferred (403/033). Personal Anthropic (+ optional OpenAI) instead. |

## Week 5 ship

- Public README with architecture and how to run
- `WRITEUP.md` LinkedIn/blog draft
- `DEMO.md` recording script (you still record/upload the video)
- Repo: https://github.com/vkaladhar2385/Health-Agent

## Commands

See `COMMANDS.md`. Notes: `NOTES.md`.
