# AGENTS.md

This file is the persistent project guide for Codex CLI sessions in this repository.

## Product Direction

Haro is a conversational AI service similar to ChatGPT, but its key distinction is that every project gets an independent physical file workspace.

Users can continue multiple chats inside one project. The AI agent goes beyond answering questions: it can create, edit, search, delete, and organize files and folders in the project workspace to produce real artifacts.

The current implementation direction is a single-agent architecture. One agent handles intent analysis, planning, and tool execution. A skill system based on MCP/FastMCP remains an extension direction, but the active execution path is currently centered on backend built-in tools.

## Core Architecture

The primary flow is `Project` + `ChatSession`. Treat `Session`, `Todo`, `Chat.svelte`, `sessions.ts`, and similar early paths as legacy compatibility surfaces. New features should prefer the project/chat-session structure.

Request flow:

```text
User browser
  -> Svelte SPA
  -> FastAPI API
  -> POST /api/projects/{project_id}/chats/{chat_id}/messages
  -> SSE streaming response
  -> run_agent()
      -> save user message
      -> resolve intent gate
      -> resolve execution policy and selected tool hints
      -> stream Gemini response
      -> parse tool_call JSON block
      -> execute backend built-in tool
      -> record file changes, logs, debug traces, and preview events
```

Main technology stack:

- Backend: FastAPI, SQLAlchemy async, SQLite
- Frontend: Svelte 5, Vite, svelte-spa-router
- Realtime: SSE over the POST response
- Authentication: JWT bearer token and bcrypt password hash
- LLM: Google Gemini API
- File storage: local filesystem workspaces
- File index: per-workspace `.haro/db/workspace.db`
- Code execution and preview: Docker SDK with `denoland/deno:latest`

Understand agent tool execution through `src/backend/app/services/tool_registry.py` and `src/backend/app/services/agent_tools.py`. Docker code execution and web preview behavior are handled by `src/backend/app/services/container_manager.py` and related container modules.

## Repository Layout

```text
.
  AGENTS.md    Persistent repository instructions for Codex sessions
  .specs/      Specs, implementation notes, verification notes, and linked commits
  DESIGN.md    Design guide
  doc/         Product, technical, marketing, and implementation documents
  docs/        Public English contributor documentation
  scripts/     Helper scripts
  src/         Product source code and planning notes
  study/       Study and reference material
  tmp/         Temporary working files
```

`src` structure:

```text
src/
  backend/           FastAPI backend
  frontend/          Svelte 5 + Vite frontend
  sandbox-runtime/   Experimental standalone sandbox runtime
  plan/              Product and architecture planning notes
```

`doc/src/README.md` is the current implementation summary for `src`. Read it first before source-level work, then read the actual code.

## Work Principles

- Read relevant files before changing code.
- Modify only files directly connected to the request.
- Prefer existing style and current architecture.
- State assumptions when something is uncertain.
- Ask before risky choices or irreversible changes.
- Mention unrelated legacy code when useful, but do not clean it up unless asked.
- When changing file operations, agent tools, or workspace policy, also check `doc/src/README.md` and `src/plan`.

## Code Design and Testing

Backend feature changes and refactors should include unit tests. If the current shape is hard to test, first extract a pure helper or small module and test that boundary. If tests truly cannot be added, explain why and state the remaining risk.

Backend code should be strongly modular. Classes, modules, and functions should follow single-responsibility boundaries. Use facade-style orchestration when a flow composes several smaller services, but only when it improves responsibility separation, testability, and caller simplicity.

Line count is only a signal, not a hard rule. Files over 300 lines deserve inspection, but they can be acceptable if they still have one clear responsibility. Smaller files can still need refactoring if UI, data loading, domain policy, infrastructure calls, and formatting logic are mixed together.

When evaluating a large file, ask:

- Could this file or class change for several unrelated reasons?
- Are UI rendering, data loading, policy, infrastructure calls, and formatting mixed unnecessarily?
- Is core logic hard to test without a large external system or screen state?
- Is a composition/facade responsibility clearly separated from internal detailed responsibilities?

Facade modules, route components, and router modules can compose multiple lower-level modules. If they start owning detailed policy or algorithms, split those details into internal modules.

When the user explicitly asks to continue through a known set of remaining files or refactor candidates, handle the identified candidates one by one. For each responsibility unit, add or update focused tests where practical, run verification, and update relevant spec documentation when needed.

Frontend code should use Svelte components, stores, and utilities to keep responsibilities separate. If one screen mixes file exploration, chat, viewer, debug, deployment, and domain policy, split it into smaller components and helpers.

## Runtime Commands

Default development ports:

- Backend: `8001`
- Frontend: `5174`

On Windows local development, keep the backend default bind host at `127.0.0.1`.

After changing files that directly affect running development servers, such as server startup code, environment settings, dependencies, agent prompts, tools, or harness policy, restart the affected server automatically unless the user says not to. Before and after restart, check the listening PID and health check for the target port. Kill only the process bound to that development server port.

Normal frontend code changes usually do not need a restart because Vite HMR can handle them. Restart the frontend only for changes such as `vite.config`, `.env`, dependencies, dev-server settings, or HMR failure.

Prefer VS Code tasks when practical. The repository has `.vscode/tasks.json` with:

- `dev: backend (8001)`
- `dev: frontend (5174)`
- `dev: all (8001 + 5174)`
- `dev: frontend fallback (5341)`
- `dev: all fallback (8001 + 5341)`

If Windows reports `EACCES` because port `5174` is in an excluded TCP range, use fallback port `5341`. In that case the frontend URL is `http://localhost:5341`.

The Python backend must use a virtual environment. Do not install packages directly into the global Python environment. The default virtual environment path is `src/backend/.venv`.

The VS Code backend task and `scripts/start-backend.ps1` try to start a local SearXNG container (`haro-searxng`, `http://127.0.0.1:8080`) before the backend starts. They inject `WEB_SEARCH_PROVIDER=searxng` and `WEB_SEARCH_BASE_URL=http://127.0.0.1:8080` into the backend process. If Docker is off, the backend can still run, but the `web_search` tool will not work until SearXNG is available.

When restarting the backend, do not directly call `python -m uvicorn ...` unless the user explicitly asks to run without web search. Direct `uvicorn` startup can miss `WEB_SEARCH_BASE_URL` and break the previously working `web_search` tool. Prefer `scripts/start-backend.ps1` or `scripts/run-backend-dev.ps1`.

Run backend:

```powershell
.\scripts\run-backend-dev.ps1 -Reload
```

Manual backend startup for exceptional debugging without SearXNG:

```powershell
cd src/backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Run backend tests:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

Run frontend:

```powershell
cd src/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5174
```

Run frontend tests and build:

```powershell
cd src/frontend
npm test
npm run build
```

Default URLs:

- Frontend: `http://localhost:5174`
- Backend health check: `http://localhost:8001/api/health`
- Backend default CORS origin: `http://localhost:5174`

Check Docker sandbox prerequisites:

```powershell
docker version
docker info
docker image inspect denoland/deno:latest
```

Pull the default sandbox image if needed:

```powershell
docker pull denoland/deno:latest
```

Code execution and web preview require a working Docker daemon. If Docker is off, login, project, and file APIs should still work where possible, but `code_run`, `web_preview`, deploy, and preview paths can fail. For sandbox issues, check Docker daemon state, the `denoland/deno:latest` image, backend `.env` `SANDBOX_*` settings, and the project `container_status`.

## Spec-Driven Development

For changes that are not trivial and have product or architecture significance, strongly prefer writing a spec first. Even if the user asks for immediate implementation, suggest a spec briefly when the work affects:

- data models, API contracts, SSE events, agent routing, tool execution, or workspace policy
- frontend and backend behavior together
- existing user data, file workspaces, Docker sandbox behavior, authentication, or authorization
- work that naturally belongs in multiple commits
- ambiguous requirements or decisions that are hard to reverse after implementation

Before implementing a spec, review the strategy again. Ask internally whether the strategy is effectively certain. If not, identify gaps, failure conditions, data-loss risk, irreversible decisions, and UX gaps. Fix the strategy until it is defensible.

Specs live under:

```text
.specs/draft/{spec}/
.specs/work/{spec}/
.specs/done/{spec}/
```

Use a short meaningful kebab-case `{spec}` name.

When creating a new spec, first write only `.specs/draft/{spec}/spec.md` and confirm the problem, goals, non-goals, and success criteria with the user. Do not create `design.md`, `plan.md`, `tasks.md`, `implementation.md`, or `commits.md` all at once before the spec direction is accepted.

Lifecycle:

- `.specs/draft/{spec}/`: idea, problem definition, or design draft before implementation starts
- `.specs/work/{spec}/`: implementation, verification, or documentation sync in progress
- `.specs/done/{spec}/`: implementation, verification, documentation sync, and linked commit tracking completed

Move specs from `draft` to `work` when implementation starts, and from `work` to `done` when the work is complete.

Recommended files:

- `spec.md`: problem, goals, non-goals, user flow, success criteria
- `design.md`: architecture, data model, API/SSE contracts, UI impact, alternatives, decisions
- `implementation.md`: implementation result, changed files, verification, remaining work
- `commits.md`: linked commit hashes, branch, PR, deployment, or release notes

When implementing work that has a spec, keep `implementation.md` and `commits.md` current. When asked to commit, also check whether linked spec documents need synchronization.

## Commits, Pushes, and Documentation Sync

Do not commit or push just because work is complete. Commit and push only when the user explicitly asks.

When committing:

1. Inspect `git status` and relevant diffs to separate your changes from existing user changes.
2. If code changes affect documented architecture, APIs, workspace policy, tools, or execution flow, synchronize the relevant docs.
3. Run practical verification commands and record anything that could not be run.
4. Stage only files in scope. Do not stage unrelated changes or user-made changes.
5. Commit with a clear message.
6. Push only if the user asked for push or the context clearly means commit plus push. If the remote or branch is unclear, ask before pushing.

Documentation sync is part of code work. In particular, changes to `src` structure, agent tools, SSE events, data models, workspace policy, or execution commands may require updates to `doc/src/README.md`, `src/plan`, or related docs.

After committing, summarize:

- what code, configuration, or documentation changed
- which docs were synchronized, or why no doc sync was needed
- tests, builds, lint, scans, or manual checks that were run
- remaining risks, technical debt, or test gaps
- commit hash, branch, and push status
