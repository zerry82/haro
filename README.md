# Haro

[![License: MIT](https://img.shields.io/badge/license-MIT-0f766e.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-2563eb.svg)](src/backend)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-059669.svg)](src/backend)
[![Svelte](https://img.shields.io/badge/frontend-Svelte%205-ff3e00.svg)](src/frontend)
[![Docker](https://img.shields.io/badge/sandbox-Docker-2496ed.svg)](src/backend/app/services/container_manager.py)

Haro is an open-source AI workspace for project-based work. It combines chat,
files, code execution, previews, and workspace memory into one local-first
product surface.

Haro's product vision is more specific than a generic AI workspace: Haro is an
active sandbox AI agent for marketers.

It is designed for the people who live between campaign strategy, ad operations,
creative production, reporting, and client communication. A marketer should be
able to bring a campaign brief, Meta/Google ad data, reference files, audience
notes, creative requirements, and reporting goals into one project, then ask the
agent to actively work inside that project.

The ambition is for Haro to become the marketer's always-on execution room:
one place where the AI can inspect campaign context, organize files, draft
reports, prepare banners, generate video-production briefs, assemble landing or
dashboard previews, and keep the campaign's working memory intact.

Haro is currently a developer preview. The architecture is production-minded,
but the project is still moving quickly and should be treated as an early
open-source codebase.

## Why Haro

Modern marketers do not need another passive chatbot. They need an agent that
can sit inside the messy campaign workspace and help move work forward.

Haro is being built around that idea:

- Campaign work should have a durable workspace, not disappear into chat history.
- Marketing context should include files, briefs, ad-platform data, drafts,
  reports, and decisions.
- The agent should be able to create and revise real artifacts, not just suggest
  what a human should do next.
- Marketers should be able to experiment in a sandbox before anything reaches a
  client, ad account, or production channel.
- Creative and performance work should live together: strategy, Meta/Google ad
  operations, banners, video concepts, reporting, and follow-up.

## Marketing Workflows Haro Wants To Own

Haro is aimed at the daily work loop of performance marketers, agencies, growth
teams, and operators who manage campaigns across channels.

- **Meta and Google ad operations**: organize campaign files, compare report
  inputs, prepare analysis notes, and turn messy performance context into a
  concrete next action.
- **Campaign reporting**: transform raw files, search prior context, create
  markdown/HTML reports, and prepare previewable dashboards.
- **Banner production**: turn campaign briefs and creative requirements into
  structured banner concepts, copy variants, asset checklists, and production
  briefs.
- **Video production planning**: draft short-form video concepts, shot lists,
  scripts, storyboard notes, review checklists, and handoff documents.
- **Client and team communication**: keep decisions, references, and follow-up
  messages attached to the project instead of scattering them across chat,
  email, and files.
- **Active experimentation**: run code, preview generated pages, inspect files,
  and iterate inside a project sandbox before shipping anything externally.

## What Haro Is Today

Haro is a developer preview of that vision. The current codebase already focuses
on the foundation that this kind of marketer agent needs:

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

The creative-production and ad-operations vision is intentionally larger than
the current implementation. The repository is the foundation: workspace memory,
agent tools, sandbox execution, previews, and context handling.

## Product Surface

For users, Haro is organized as a project workspace:

- Left: project navigation, file explorer, tools, skills, and mail/context panels.
- Center: file viewer, markdown/HTML/CSV preview, code view, and editor.
- Right: project chat sessions and streamed agent activity.

For developers, Haro ships as a FastAPI backend and a Svelte 5 single-page app.

```text
Browser
  -> Svelte workspace UI
  -> FastAPI API
  -> Project + ChatSession storage
  -> Streaming agent loop
  -> Workspace files, Docker sandbox, previews, logs, debug traces
```

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
