# Pipeline Health Agent — useful commands

Run from the project root:

```powershell
cd c:\Vis\MyLearning\agentic-ai-mcp\Health-Agent
```

Secrets in `.env` (gitignored): `ANTHROPIC_API_KEY`, optional `OPENAI_API_KEY`, `PHA_MODEL`, `PHA_PROVIDER`.

---

## Setup

| Command | When |
| --- | --- |
| `uv sync` | After clone or dependency changes |
| `uv add <package>` | Add a dependency |
| `uv run <cmd>` | Run inside the project env |

---

## Diagnose / HITL

```powershell
uv run pha diagnose --pipeline egress
uv run pha resume --thread <id> --decision approve
uv run pha diagnose --pipeline egress --decision approve
```

Faults: `none`, `consumer_lag_spike`, `high_error_rate`, `schema_mismatch`, `partition_hotspot`, `ambiguous`, `prompt_injection`.

```powershell
uv run pha diagnose --pipeline egress --fault prompt_injection
```

Healthy / injection cases finish with action `none` (no write approval).

---

## Memory and audit

```powershell
uv run pha memory
uv run pha memory --pipeline egress
uv run pha audit
```

`pha audit` shows who approved/rejected which write action and when (`PHA_ACTOR` or Windows username).

---

## Observability dashboard (Week 4)

```powershell
uv run pha dashboard
uv run pha dashboard --open
```

Writes `.pha/dashboard.html` with per-run latency, tokens, and estimated cost. Open in a browser for the Week 4 screenshot.

---

## Evaluation

```powershell
uv run pha-eval
uv run pha-eval --limit 5
uv run pytest
```

---

## Model swap / compare

```powershell
# Use OpenAI instead of Claude (requires OPENAI_API_KEY in .env)
# PHA_PROVIDER=openai
# PHA_MODEL=gpt-4o-mini

uv run pha-compare
```

Runs a small fixed pack on Anthropic, then OpenAI if `OPENAI_API_KEY` is set.

---

## MCP

```powershell
uv run pha-mcp
```

---

## Local state (do not commit)

| Path | Purpose |
| --- | --- |
| `.env` | API keys / model / provider |
| `.pha/checkpoints.sqlite` | Pause/resume |
| `.pha/incidents.sqlite` | Incident memory |
| `.pha/traces.sqlite` | Run traces |
| `.pha/audit.sqlite` | Approval audit log |
| `.pha/dashboard.html` | Cost/latency dashboard |

```powershell
Remove-Item -Recurse -Force .pha
```

---

## Demo sequences

### Week 2 HITL
```powershell
uv run pha diagnose --pipeline egress
uv run pha resume --thread <id> --decision approve
uv run pha memory --pipeline egress
```

### Week 3 eval
```powershell
uv run pha-eval
```

### Week 4 exit checks
```powershell
uv run pha diagnose --pipeline egress --fault prompt_injection
uv run pha diagnose --pipeline egress --decision approve
uv run pha dashboard --open
uv run pha audit
uv run pha-eval --limit 5
```
