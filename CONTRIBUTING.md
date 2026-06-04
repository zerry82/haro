# Contributing to Haro

Thanks for taking the time to contribute. Haro is an early project, so the most
valuable contributions are focused, well-tested, and easy to review.

## Ground Rules

- Keep changes scoped to the problem being solved.
- Prefer the existing architecture over new abstractions.
- Add tests for backend behavior changes.
- Avoid committing generated runtime data, local workspaces, credentials, or
  private project artifacts.
- For product or architecture changes, write a short spec before implementation.

## Development Setup

Install backend dependencies:

```bash
cd src/backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Install frontend dependencies:

```bash
cd src/frontend
npm install
```

Enable local Git hooks:

```bash
git config core.hooksPath .githooks
```

## Test Before Opening a Pull Request

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

Secret scan:

```powershell
.\scripts\scan-secrets.ps1 -All
```

If a check cannot be run, mention why in the pull request.

## Spec-Driven Changes

Create or update a spec for changes that affect:

- API contracts or SSE events
- database models or migrations
- agent routing, tool policy, or prompt contracts
- workspace file policy
- Docker sandbox execution or preview behavior
- frontend and backend behavior together

Specs live under `.specs/`:

```text
.specs/draft/{name}/
.specs/work/{name}/
.specs/done/{name}/
```

Start with `spec.md`. Add design and implementation notes only after the
problem and success criteria are clear.

## Pull Request Checklist

- The change is scoped and described clearly.
- Tests were added or updated where needed.
- Documentation was updated if behavior changed.
- `src/backend/.env` and other local secrets were not committed.
- Runtime data under `data/`, `runtime/`, `tmp/`, and `study/` was not included.

## Code Style

Backend code should keep responsibilities small and testable. Prefer pure
helpers around complex logic and use facade-style orchestration when multiple
services need to be composed.

Frontend code should keep UI presentation, state management, API calls, and
domain logic separated. Use existing Svelte components, stores, and theme
tokens before introducing new patterns.
