# Commits

## 2026-05-14

- Branch: `main`
- Commit: `57c60cf` (`Add Gemini explicit prompt cache`)
- Scope:
  - Split prompt assembly into cached stable system prompt and runtime context.
  - Added Gemini explicit cache file store with 300 second TTL and fallback path.
  - Added prompt macros for full/cached/runtime prompt debug views.
  - Updated backend/frontend tests and implementation docs.
- Validation:
  - `src/backend/.venv/Scripts/python.exe -m pytest`
  - `npm test`
  - `npm run build`
  - Backend health check: `GET /api/health` returned 200 after restart.
