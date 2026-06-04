# Roadmap

Haro is currently a developer preview. The immediate goal is to make the
project workspace model reliable, inspectable, and safe enough for serious
local use.

## Near Term

- Stabilize the single-agent execution loop.
- Improve tool result formatting and user-visible progress.
- Keep file operations surgical and auditable.
- Strengthen workspace path policy and hidden metadata protection.
- Expand focused backend unit tests for routing, tools, and sandbox recovery.
- Improve frontend component boundaries around workspace, chat, files, and
  debug traces.

## Agent Runtime

- Better context compaction across long project sessions.
- More explicit tool policy decisions for destructive or high-risk actions.
- Richer debug traces for prompt cache, runtime guidance, and tool loops.
- Safer recovery behavior when Docker containers become stale.
- Better handling of large CSV and generated dashboard workflows.

## Workspace and Files

- Better file index maintenance for large workspaces.
- Stronger distinction between final artifacts, working files, hidden metadata,
  and imported context.
- Improved project export flows.
- More predictable artifact placement for chat-generated outputs.

## Integrations

- Continue the Gmail/context-library experiments.
- Keep external connector data explicit, reviewable, and approved before it is
  promoted into project context.
- Treat MCP/FastMCP support as an extension direction, while the current
  execution path remains backend built-in tools.

## Frontend

- Improve workspace density without making the UI feel like a developer-only
  tool.
- Make debug mode easier to scan.
- Improve mobile and narrow-width behavior.
- Add richer previews for common document and data artifacts.

## Not in Scope Right Now

- A multi-agent team-manager architecture.
- Production SaaS deployment defaults.
- Public marketplace distribution for skills or plugins.
- Replacing backend built-in tools with MCP as the main execution path.
