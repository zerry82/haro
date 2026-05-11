# Claude-Style Plan Mode Implementation

## 2026-05-09

- Added backend Plan Mode persistence with `PlanSession`, `PlanEvent`, and `ExecutionTodo`.
- Added `plan_mode` service helpers for session state, approval/reject, plan file paths, allowlists, and prompt instructions.
- Added `plan_file_update` and `plan_approval_request` tools.
- Integrated Plan Mode into message execution:
  - UI/requested or router-suggested Plan Mode creates a plan session.
  - Plan Mode allows read tools plus plan-file updates and approval requests.
  - Execution tools are blocked until approval.
  - Approval runs the approved plan through the existing agent tool loop.
- Added Plan Mode state API at `GET /api/projects/{project_id}/chats/{chat_id}/plan-mode`.
- Added frontend Plan Mode store, header toggle, Plan badge, approval card, and approve/reject actions.
- Added backend and frontend tests for Plan Mode routing, allowlist, blocking, payloads, and SSE state updates.

## Verification

- `cd src/backend; .\.venv\Scripts\python.exe -m pytest`
- `cd src/frontend; npm test`
- `cd src/frontend; npm run build`
- `git diff --check`

## 2026-05-10 Follow-up: Approved Plan File Operations

- Added native `file_move` and `dir_delete` tools so approved folder-organization plans can mutate the real workspace and refresh the workspace file DB.
- Updated routing/tool instructions to select native file tools for folder cleanup and to stop using `code_run` as a workspace file-operation fallback.
- Updated frontend tool labels/catalog entries for the new file-operation tools.
- Added targeted backend tests for folder cleanup routing and native move/delete execution.

## 2026-05-10 Follow-up: Local Folder Plans Do Not Need Web Evidence

- Narrowed Plan Mode evidence detection so local workspace/folder organization plans are not treated as external research just because category names contain words like research, analysis, dashboard, or report.
- Kept web evidence requirements for genuinely external/current-data work such as latest investment research reports.
- Updated Plan Mode instructions to say evidence is required for external-fact/latest-data plans, not for local file organization.
- Added regression coverage for a `30_outputs` folder cleanup plan that uses research/dashboard folder names without requiring `web_search`.
