Backend service for Perfect Report.

Run locally:

```powershell
uv sync --dev
uv run uvicorn report_backend.main:app --reload --host 127.0.0.1 --port 8000
```

Current source layout:

```text
backend/
  src/report_backend/
    api/
      routes/
    core/
    domain/
    integrations/
    parsers/
    services/
    workflows/
```
