# Haro Architecture

This document summarizes the current implementation for English-speaking
contributors. The more detailed implementation notes are in `doc/src/README.md`.

## High-Level Flow

```text
User browser
  -> Svelte SPA
  -> FastAPI API
  -> POST /api/projects/{project_id}/chats/{chat_id}/messages
  -> SSE streaming response
  -> run_agent()
      -> save user message
      -> resolve intent and execution policy
      -> build prompt bundle and runtime context
      -> stream Gemini response
      -> parse tool_call JSON blocks
      -> execute backend built-in tools
      -> record file changes, logs, previews, and debug traces
```

The active product model is `Project` + `ChatSession`. Older `Session`, `Todo`,
`Chat.svelte`, and `sessions.ts` paths still exist for compatibility and should
not be treated as the primary design direction for new features.

## Backend

The backend is a FastAPI application using SQLAlchemy async and SQLite.

Main responsibilities:

- authentication and user sessions
- project and chat lifecycle
- file APIs and workspace indexing
- streamed message execution
- agent orchestration
- tool policy and tool execution
- Docker sandbox lifecycle
- web preview proxying
- optional Gmail/context workflows

Key modules:

| Module | Responsibility |
|---|---|
| `app/main.py` | Application entrypoint. |
| `app/app_factory.py` | App construction and route registration. |
| `app/config.py` | Environment-backed settings. |
| `app/database.py` | Async SQLAlchemy setup. |
| `app/routers/messages.py` | Chat message streaming endpoint. |
| `app/services/agent.py` | Main agent orchestration. |
| `app/services/agent_tool_loop.py` | Tool loop execution. |
| `app/services/tool_registry.py` | Built-in tool catalog. |
| `app/services/agent_tools.py` | File and workspace tool implementation. |
| `app/services/container_manager.py` | Docker sandbox facade. |
| `app/services/workspace_file_db.py` | Workspace file index. |

## Frontend

The frontend is a Svelte 5 SPA built with Vite.

Main responsibilities:

- authentication screens
- project dashboard
- project workspace route
- file explorer and viewer
- CodeMirror-based editor
- chat sessions and streamed agent messages
- debug trace modal
- mail/context panels

Important frontend paths:

| Path | Responsibility |
|---|---|
| `src/frontend/src/App.svelte` | SPA route map. |
| `src/frontend/src/routes/ProjectWorkspace.svelte` | Main workspace screen. |
| `src/frontend/src/stores/chat.ts` | Message sending and SSE handling. |
| `src/frontend/src/stores/files.ts` | File tree, search, read, save, upload. |
| `src/frontend/src/lib/sse.ts` | Fetch-stream SSE parser. |
| `src/frontend/src/theme.css` | Shared visual design tokens. |

## Agent Runtime

Haro currently uses a single-agent runtime. The agent decides how to proceed
within a backend-defined policy and tool catalog. It is not a team-of-agents
manager.

Execution outline:

1. Save the user message.
2. Resolve message gate and execution policy.
3. Build stable prompt and runtime context.
4. Prepare Gemini explicit prompt cache when possible.
5. Stream model output.
6. Parse the final `tool_call` fenced JSON block.
7. Apply tool policy.
8. Execute backend tools.
9. Return tool results to the model.
10. Repeat until completion or limit.

The tool catalog includes file creation, reading, editing, search, export,
directory operations, code execution, web preview, web search, batching, and
mail/context tools.

## Workspaces

Each project has a physical workspace, usually under:

```text
data/workspaces/{user_id}/{project_id}
```

The workspace is structured to separate immutable context, user work, chat
artifacts, and hidden metadata:

```text
clean-room/
playground/
  users/{user_id}/
    00_inbox/
    20_working/
    30_outputs/
    40_rules/
    45_skills/
    50_chats/
90_archive/
.haro/
```

The `.haro` directory contains internal metadata and indexes. It is not a user
editing target.

## Docker Sandbox

Code execution and web previews use Docker. The backend creates and manages
per-project containers, mounts the workspace, executes scripts, and proxies
preview traffic.

The default sandbox image is:

```text
denoland/deno:latest
```

Docker is optional for basic auth, projects, chat, and file APIs, but required
for `code_run`, `web_preview`, and deploy/preview workflows.

## Current Design Direction

The current direction is:

- single-agent orchestration
- backend built-in tools
- project-scoped file workspaces
- explicit path and metadata policy
- inspectable debug traces
- spec-driven larger changes

MCP/FastMCP-based skills remain an extension direction, but they are not the
main execution path today.
