# 3-minute demo script

Record this as a screen + voice walkthrough. Target: **fault → diagnosis → approval → fix → trace**.

## Setup (before recording)

```powershell
cd c:\Vis\MyLearning\agentic-ai-mcp\Health-Agent
uv sync
# .env already has ANTHROPIC_API_KEY
Remove-Item -Recurse -Force .pha -ErrorAction SilentlyContinue
```

Have two terminals ready, or one terminal plus browser.

## Script (~3:00)

### 0:00–0:20 — Problem (talking head or README)

> “This is a Pipeline Health Agent for mock streaming pipelines. It diagnoses faults from metrics, logs, and deploys. Any remediation pauses for a human. No real customer data.”

Show the architecture block in `README.md` for 5 seconds.

### 0:20–1:20 — Fault and diagnosis

```powershell
uv run pha diagnose --pipeline egress
```

Narrate while it runs:

> “I inject a consumer lag spike on egress. The graph triages metrics, searches logs, checks deploys, then diagnoses.”

When it pauses, highlight:

- Diagnosis naming **lag** and **`max.poll.records`**
- Proposed action **`restart_consumer`**
- Printed **thread id**

> “It will not restart anything until I approve.”

### 1:20–1:50 — Approval and fix

```powershell
uv run pha resume --thread <paste-id> --decision approve
```

> “I approve. The remediation is simulated, then the incident is saved to memory.”

Show `decision: approve` and `remediation.status: simulated_ok`.

### 1:50–2:20 — Memory and audit

```powershell
uv run pha memory --pipeline egress
uv run pha audit
```

> “Memory stores the incident for later ‘seen this before’ context. The audit log records who approved what and when.”

### 2:20–2:45 — Trace dashboard

```powershell
uv run pha dashboard --open
```

Point at latency and estimated cost columns.

> “Every run is traced locally: steps, tokens, cost, latency. No Docker required for this dashboard.”

### 2:45–3:00 — Close

Optional 10-second cut:

```powershell
uv run pha diagnose --pipeline egress --fault prompt_injection
```

> “Prompt injection in a log line does not change the action. Healthy stays healthy.”

End on the repo URL:

> “Clone it and run from the README: github.com/vkaladhar2385/Health-Agent”

## After recording

1. Upload unlisted or public to YouTube / Loom.
2. Paste the link into the README under **Demo** (optional one-liner).
3. Add the repo + video link to LinkedIn and resume.

## Fallback if live model is slow

Use the one-shot form and narrate the pause conceptually:

```powershell
uv run pha diagnose --pipeline egress --decision approve
```

Still show memory, audit, and dashboard afterward.
