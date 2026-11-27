# CLAUDE.md — The Grove

The Grove (grove.substep.co) is a private daily companion: chat or journal, then a
tradition-specific guided meditation. Full spec: docs/SPEC.md. Read it before large changes.

## Stack
- web/: SvelteKit 3 + TypeScript + Tailwind 4. Font Lato. Deployed on Vercel.
  SvelteKit 3 idioms: env vars are declared in web/src/env.ts and imported from `$app/env/public`
  (not `$env/*`); local modules are imported as `#lib/<file>.js` (not `$lib`).
- api/: Python 3.12, FastAPI, LangGraph, LangChain chat models. Managed with uv.
- Supabase Postgres + pgvector; LangGraph PostgresSaver (threads) and PostgresStore (memory).
- Cloudflare R2 for audio/images. ElevenLabs for voices. Claude (Sonnet 5.5 / Haiku 5.5) for text; Gemini for images, embeddings, OCR.

## Local-first
- The app must boot and pass `make check` with NO external API keys: every outside service
  has a mock or local adapter selected by env var (see docs/SPEC.md, Local development setup).
- Never read or print `.env` files; use `.env.example` for variable names.

## Rules
- Traditions are content: never hard-code tradition logic in Python; read traditions/<id>/.
- Guides never speak as founders, deities or religious figures. No invented quotations.
- Journal text is always encrypted before insert; never log it, never send it to tracing.
- Every user-facing input passes through the guard node first. Do not bypass it.
- No streaks, badges or push-notification nudges.
- Model choice lives in config (api/app/config.py), never inline in nodes.

## Commands
- all: make dev | make check | make check-db | make seed | make env
- web: pnpm dev | pnpm test | pnpm lint
- api: uv run fastapi dev | uv run pytest | uv run python -m evals.safety
- db: supabase start | supabase db reset

## Working style
- Work milestone by milestone (docs/SPEC.md, Build milestones). Finish and test one before starting the next.
- Show evidence when you finish: the commands you ran and their output.
- Ask before adding a dependency or changing the data model.
- After each milestone, update the checklist in docs/SPEC.md.
