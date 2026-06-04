# Development Guide

This guide covers local development for Haro.

## Repository Layout

```text
.
  README.md
  AGENTS.md
  DESIGN.md
  .specs/
  doc/
  docs/
  scripts/
  src/
    backend/
    frontend/
    sandbox-runtime/
    plan/
```

## Backend Setup

```bash
cd src/backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Windows PowerShell activation:

```powershell
.\.venv\Scripts\Activate.ps1
```

Configure environment:

```bash
cp src/backend/.env.example src/backend/.env
```

Set at least:

```text
GEMINI_API_KEY=your_gemini_api_key
JWT_SECRET=your_jwt_secret_change_this
```

Run backend:

```bash
cd src/backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Windows helper script:

```powershell
.\scripts\run-backend-dev.ps1 -Reload
```

The helper attempts to start local SearXNG and inject web-search environment
variables when available.

## Frontend Setup

```bash
cd src/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5174
```

Open:

```text
http://localhost:5174
```

## Docker Sandbox

Install Docker and pull the default image:

```bash
docker pull denoland/deno:latest
```

Useful checks:

```bash
docker version
docker info
docker image inspect denoland/deno:latest
```

Without Docker, basic APIs can still run, but code execution and preview
features will fail.

## Tests

Backend:

```bash
cd src/backend
pytest
```

Frontend:

```bash
cd src/frontend
npm test
npm run build
```

## Secret Scanning

Run:

```powershell
.\scripts\scan-secrets.ps1 -All
```

Scan only staged files:

```powershell
.\scripts\scan-secrets.ps1 -Staged
```

Enable the versioned pre-commit hook:

```bash
git config core.hooksPath .githooks
```

## Spec Workflow

Use specs for larger changes, especially changes involving:

- data models
- APIs or SSE events
- agent routing and tool policy
- workspace file policy
- Docker sandbox behavior
- frontend and backend contracts together

Spec lifecycle:

```text
.specs/draft/{spec}/
.specs/work/{spec}/
.specs/done/{spec}/
```

Start with `spec.md`, then add design and implementation notes as the work
becomes concrete.

## Common Ports

| Service | URL |
|---|---|
| Frontend | `http://localhost:5174` |
| Backend | `http://localhost:8001` |
| Backend health | `http://localhost:8001/api/health` |
| Local SearXNG | `http://127.0.0.1:8080` |

If port `5174` is unavailable on Windows, use the fallback frontend task or run
Vite on another port and update backend CORS settings.
