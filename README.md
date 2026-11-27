# The Grove

A private daily companion: chat or journal, then a tradition-specific guided meditation.
Spec: [docs/SPEC.md](docs/SPEC.md). Working rules for Claude Code: [CLAUDE.md](CLAUDE.md).

## Quickstart (no API keys needed)

Prerequisites: Docker Desktop, Node 22.17+ and pnpm, Python 3.12 and uv, Supabase CLI.

```bash
make install        # uv sync + pnpm install
make env            # create api/.env and web/.env from the examples
supabase start      # then copy keys from `supabase status -o env` into the .env files
make dev            # Supabase + API (:8000) + worker + web (:5173)
make seed           # synthetic test users and journal entries
```

Sign in at http://localhost:5173/login. The magic-link email lands in Mailpit at
http://127.0.0.1:54324.

## Verification

- `make check`: lint, type checks, pytest, Vitest, safety and tradition evals. Offline, mocks only.
  A Claude Code Stop hook runs this before a turn can end.
- `make check-db`: resets the local DB from `supabase/migrations/` and runs the RLS tests.
- `make check-live`: real models and voices (costs money; from M5).

Every outside service has a mock adapter selected by env var; see `api/.env.example`.
