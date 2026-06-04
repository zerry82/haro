# Haro

[![License: MIT](https://img.shields.io/badge/license-MIT-0f766e.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-2563eb.svg)](src/backend)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-059669.svg)](src/backend)
[![Svelte](https://img.shields.io/badge/frontend-Svelte%205-ff3e00.svg)](src/frontend)
[![Docker](https://img.shields.io/badge/sandbox-Docker-2496ed.svg)](src/backend/app/services/container_manager.py)

Haro is an open-source AI workspace for project-based work. It combines chat,
files, code execution, previews, and workspace memory into one local-first
product surface.

The core idea is simple: every project gets its own physical file workspace.
An AI agent can answer questions, create files, edit documents, search the
workspace, run code in a Docker sandbox, and stream its work back to the UI in
real time.

Haro is currently a developer preview. The architecture is production-minded,
but the project is still moving quickly and should be treated as an early
open-source codebase.

## Why Haro

Most AI chat tools are optimized around messages. Haro is optimized around
workspaces.

- Project-scoped file systems for durable work, not throwaway chat context.
- Multi-chat project history with shared artifacts and references.
- Agent tools for file creation, reading, editing, search, export, code
  execution, web preview, web search, and mail/context workflows.
- Server-sent event streaming for responsive agent progress and tool output.
- Docker-backed sandbox execution for code runs and local web previews.
- Workspace indexing with SQLite and optional full-text search.
- Debug traces for inspecting gate decisions, LLM payloads, tool calls, and
  runtime guidance.
- Gmail/context-library experiments for turning approved external context into
  workspace knowledge.
- Local secret scanning and ignore rules to reduce accidental credential leaks.

## Product Surface

Haro ships as a FastAPI backend and a Svelte 5 single-page app.

```text
Browser
  -> Svelte workspace UI
  -> FastAPI API
  -> Project + ChatSession storage
  -> Streaming agent loop
  -> Workspace files, Docker sandbox, previews, logs, debug traces
```

The main workspace has three working areas:

- Left: project navigation, file explorer, tools, skills, and mail/context panels.
- Center: file viewer, markdown/HTML/CSV preview, code view, and editor.
- Right: project chat sessions and streamed agent activity.

## Architecture

```text
src/
  backend/           FastAPI API, agent runtime, tool registry, Docker manager
  frontend/          Svelte 5 + Vite workspace application
  sandbox-runtime/   Experimental standalone sandbox runtime
  plan/              Product and architecture planning notes

doc/
  src/README.md      Current implementation notes
  haro-spec/         Product scenarios and technical specs
```

Important backend modules:

- `app/services/agent.py`: main agent orchestration.
- `app/services/tool_registry.py`: built-in tool catalog.
- `app/services/agent_tools.py`: file, search, export, and workspace tools.
- `app/services/container_manager.py`: Docker sandbox lifecycle and previews.
- `app/services/workspace_file_db.py`: per-workspace file index.
- `app/routers/messages.py`: streamed chat message endpoint.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a longer English overview.

## Quick Start

### Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- Docker Desktop or Docker Engine, for code execution and previews
- A Gemini API key, configured as `GEMINI_API_KEY`

### 1. Clone and configure

```bash
git clone https://github.com/zerry82/hr.git haro
cd haro
cp src/backend/.env.example src/backend/.env
```

Edit `src/backend/.env` and set at least:

```text
GEMINI_API_KEY=your_gemini_api_key
JWT_SECRET=your_jwt_secret_change_this
```

### 2. Start the backend

On Windows PowerShell:

```powershell
.\scripts\run-backend-dev.ps1 -Reload
```

Portable manual startup:

```bash
cd src/backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

On Windows PowerShell, activate the virtual environment from `src/backend` with:

```powershell
.\.venv\Scripts\Activate.ps1
```

The backend health check is:

```text
http://localhost:8001/api/health
```

### 3. Start the frontend

```bash
cd src/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5174
```

Open:

```text
http://localhost:5174
```

### 4. Optional sandbox image

Code execution and web preview features use Docker. Pull the default sandbox
image ahead of time:

```bash
docker pull denoland/deno:latest
```

## Development

Backend tests:

```bash
cd src/backend
pip install -r requirements-dev.txt
pytest
```

Frontend tests and production build:

```bash
cd src/frontend
npm test
npm run build
```

Secret scan:

```powershell
.\scripts\scan-secrets.ps1 -All
```

Enable the versioned Git hook in your local clone:

```bash
git config core.hooksPath .githooks
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed commands and
environment notes.

## Configuration

The backend reads configuration from `src/backend/.env`.

Key settings:

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Gemini model access for the agent runtime. |
| `JWT_SECRET` | Local authentication token signing secret. |
| `WORKSPACE_ROOT` | Project workspace root. |
| `CORS_ORIGINS` | Allowed frontend origins. |
| `WEB_SEARCH_PROVIDER` | Search provider, currently oriented around SearXNG. |
| `WEB_SEARCH_BASE_URL` | Search provider base URL. |
| `GOOGLE_GMAIL_CLIENT_ID` | Optional Gmail OAuth client ID. |
| `GOOGLE_GMAIL_CLIENT_SECRET` | Optional Gmail OAuth client secret. |
| `MAIL_TOKEN_ENCRYPTION_KEY` | Optional encryption key for mail token storage. |
| `SANDBOX_IMAGE` | Docker image used for sandboxed execution. |

Never commit `src/backend/.env`. It is ignored by default.

## Security

Haro includes a lightweight local secret scanner at
`scripts/scan-secrets.ps1`. It checks common API key and private-key patterns
without printing matched values.

The scanner is intentionally not a replacement for provider-side secret
rotation or GitHub secret scanning. If a credential may have been committed,
rotate it first, then clean history if needed.

See [SECURITY.md](SECURITY.md) for disclosure and reporting guidance.

## Roadmap

The active direction is a single-agent project workspace, not a team-of-agents
runtime. Planned work focuses on reliability, better context handling, richer
workspace artifacts, safer tool execution, and clearer extension points.

See [ROADMAP.md](ROADMAP.md).

## Contributing

Contributions are welcome. Start with:

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)

For larger changes, open an issue or draft spec first. This project uses
spec-driven development for changes that affect data models, API contracts,
agent routing, workspace policy, or sandbox behavior.

## License

Haro is released under the [MIT License](LICENSE).
