# The Grove — Build Spec for Claude Code

Nov 26, 2026 · @Sanjay

## Overview

The Grove (grove.substep.co) is a private daily companion: you talk or journal with a frontier model, and it offers a short guided meditation shaped by what you said and by your tradition. It is a Substep AI pet project; Sanjay is user zero, and v0 succeeds if he uses it daily for 30 days.

- **Audience:** Gen Z and Millennials, including spiritual-but-not-religious users and people who mix traditions.
- **Name system:** The Grove is the app; **the Hold** is the private journal space inside it ("Your journal lives in the Hold"). The walled-garden root of the word *paradise* (Old Persian *pairidaēza*) is the brand story.
- **Principles:**
  - Support an existing daily ritual; no streak pressure, no Hooked-style engineered triggers.
  - Traditions are represented respectfully: guides teach practices *of* a tradition, never speak *as* its founders or figures (no AI Baba, Jesus or Buddha).
  - Journal data is the most sensitive data in the system and is treated that way (see Safety, privacy and the Hold).
  - Traditions are content, not code: adding one means adding a folder.
- **Supersedes:** earlier Letta-based plans. Letta has refocused on Letta Code and is sunsetting the server-side memory tools, multi-agent tools and sleep-time agents ([Letta, Our next phase](https://letta.com/blog/our-next-phase)), so this build uses LangGraph.

## v0 scope and core loop

v0 is one loop, done well: check in, reflect, meditate, note. Everything else waits until Sanjay has used it for a month.

1. **Check in** — chat, or paste/upload a journal entry into the Hold.
2. **Reflect** — the companion responds briefly and asks at most one question.
3. **Offer** — when it fits (or on request), the companion offers a meditation with tradition, approach and length pre-selected from mood and history; the user can change any of them in one tap.
4. **Listen** — a generated script, voiced by the tradition's voice, mixed with an ambient bed in the browser, with a cover image.
5. **Note** — an optional one-line reflection afterward, saved to the Hold.
6. **Remember** — a background job updates the user profile and themes.

| In v0 | Later |
| --- | --- |
| Web app (responsive, phone-first layout) | Native wrapper (Capacitor) for lock-screen audio |
| Email magic-link sign-in | Social sign-in |
| 5 launch traditions, 8 approaches, 5–20 minute lengths | Second-wave traditions (Stoic, Islamic/Sufi, Jewish) |
| Default tradition set at onboarding, switchable per session | Blended or rotating traditions |
| Journal: paste, .txt, .md, .pdf, Day One JSON, photo of handwriting | Apple Journal, Notion, Google Docs import |
| Practice history list (the Hold) | Visual progress, insights, patterns |
| Pre-generated image library + occasional fresh images | Per-session generated art |
| Single user plus a few invited testers | Public sign-up, payments |

## Traditions, approaches and skill packs

Tradition and approach are separate settings, so 5 traditions × 8 approaches stays manageable. Each tradition ships as a skill pack folder; not every approach suits every tradition, and each pack declares which it supports.

| Tradition (pack id) | Practices to draw on | Guide voice (character, not a figure) |
| --- | --- | --- |
| Mindfulness, secular (`mindfulness`) | MBSR-style breath, body scan, noting, NSDR | Calm, neutral, contemporary |
| Buddhist (`buddhist`) | Vipassana/insight, metta, Zen sitting, walking | Warm, unhurried, spacious |
| Christian contemplative (`christian`) | Centering Prayer, Lectio Divina, Examen, breath prayer | Gentle, reverent |
| Yogic / Hindu (`yogic`) | Yoga nidra, japa/mantra, pranayama, OM | Grounded, rhythmic |
| Raja Yoga, Brahma Kumaris (`raja-yoga`) | Soul-consciousness, the soul as a point of light, remembrance of the Supreme Soul, drill | Soft, steady, clear; draws on the Murli without voicing Baba |

**Approaches (shared across packs):** breath, body scan, visualization, mantra/repetition, loving-kindness, gratitude, sleep, nervous-system regulation (somatic).

**Second wave:** Stoic reflection (`stoic`), Islamic/Sufi (`sufi`: dhikr, muraqaba), Jewish (`jewish`: hitbodedut).

**Skill pack layout** (`traditions/<pack-id>/`):

```markdown
traditions/raja-yoga/
  pack.yaml        # id, display name, supported approaches, length range, voice_id, image_style, ambient beds
  guide.md         # system prompt for the guide: stance, tone, vocabulary, what never to do
  structures.md    # script skeletons per approach (opening, settling, core, return), with pause markers
  sources/         # short public-domain or permitted excerpts and practice notes, embedded for retrieval
  avoid.md         # doctrinal pitfalls, terms not to use, impersonation rules
  evals.md         # 5-10 test prompts with what a good script must and must not contain
```

Scripts use a single pause syntax the renderer understands, e.g. `[pause 8s]`. Sanjay reviews `raja-yoga` himself; other packs get a review pass from a practitioner of that tradition before anyone else uses them.

## Agent architecture

One LangGraph graph (Python) serves every turn: a safety guard runs first, the companion is the only voice the user talks to, and meditation work is delegated synchronously to a router and tradition guide subgraphs. The companion is per-user through memory, not through separate agent instances; guides are shared and stateless.

&#91;embedded content: The Grove agent graph · one turn, from input to reflection\]

A crisis flag ends the turn at `crisis_response`; otherwise the companion either keeps chatting or, once the user accepts an offer, hands off to router, guide and render, and the after-session note loops back into memory.

| Node | Model tier | Job | Output |
| --- | --- | --- | --- |
| `guard` | Small, fast | Classify every message and journal entry for crisis risk | `ok` / `concern` / `crisis`; on `crisis`, route to `crisis_response` and stop |
| `companion` | Frontier | Reflect, ask at most one question, decide whether to offer a meditation; reads profile and recent themes from the store | Message stream; optional `offer_meditation` tool call |
| `router` | Small, structured output | Turn context into a meditation brief | `{tradition, approach, minutes, intent, mood}` |
| `guide:<pack>` | Frontier | Load the skill pack, retrieve relevant sources, write the script | Script text with `[pause Ns]` markers |
| `render` | none (tools) | Text-to-speech per segment, pick or generate image, upload to storage | `{audio_segments[], image_url, ambient}` |
| `reflect` | Frontier | After playback, invite a one-line note and save it to the Hold | Message; journal entry |
| `summarize` (background) | Small | After sessions and uploads, update profile and themes | Store writes |
| `crisis_response` | Fixed text + frontier | Respond with care and resources; no meditation offered | Message |

**Graph state:** `messages`, `user_id`, `thread_id`, `safety`, `brief`, `script`, `render_result`, `phase` (`chat` / `offering` / `playing` / `reflecting`).

**Conventions:**

- Models go through a provider-agnostic wrapper (LangChain chat models) so Gemini and Claude can be swapped per node by config.
- The user approves the meditation offer before `guide` and `render` run (LangGraph interrupt), so no text-to-speech is spent on unwanted sessions.
- The frontend streams `companion` tokens over server-sent events from FastAPI.

## Memory and data model

All state lives in one Supabase Postgres database with pgvector: LangGraph's checkpointer holds conversation threads (in a private `langgraph` schema that the Supabase REST API cannot reach), LangGraph's `PostgresStore` (with a semantic index) holds per-user memory, and plain app tables hold everything the UI lists. Row-level security restricts every app table to `auth.uid()`.

**LangGraph store namespaces** (per user: `("user", <user_id>, <kind>)`):

| Namespace | Contents | Written by |
| --- | --- | --- |
| `profile` | One document: default tradition, preferred approaches, voice/length preferences, short bio-style summary | Onboarding, `summarize` |
| `themes` | Recurring topics and moods, each with first/last seen dates | `summarize` |
| `journal_chunks` | Embedded chunks of Hold entries for semantic recall | Upload pipeline |
| `practice` | Compact per-session records the companion can recall | `render`, `reflect` |

**App tables:**

| Table | Key columns |
| --- | --- |
| `profiles` | `user_id`, `display_name`, `default_tradition`, `timezone`, `created_at` |
| `journal_entries` (the Hold) | `id`, `user_id`, `source` (`chat`/`paste`/`file`/`photo`/`dayone`/`reflection`), `body_encrypted`, `entry_date`, `created_at` |
| `sessions` | `id`, `user_id`, `thread_id`, `tradition`, `approach`, `minutes`, `intent`, `script`, `audio_keys[]`, `image_key`, `safety_flagged`, `completed_at`, `rating` |
| `uploads` | `id`, `user_id`, `filename`, `mime`, `status`, `entry_ids[]` |
| `threads` | `id` (= LangGraph `thread_id`), `user_id`, `safety_flagged`, `created_at`, `last_message_at` (no title: it would hold chat text in plaintext) |
| `image_library` | `id`, `tradition`, `theme`, `time_of_day`, `storage_key` |
| `audio_cache` | `hash` (voice + segment text), `storage_key` |

Journal bodies are encrypted at the application layer before insert (a per-user key wrapped by a server key held outside the database), so a leaked database dump does not expose entries.

## Tools and integrations

Five tools carry v0: journal upload, meditation offer, text-to-speech rendering, imagery, and history lookup. Each is a plain Python function exposed to the graph as a LangChain tool.

| Tool | What it does | Notes |
| --- | --- | --- |
| `upload_journal` | Accepts paste, .txt, .md, .pdf, Day One JSON export, or a photo of handwriting; splits into dated entries; encrypts and saves to the Hold; chunks and embeds for recall | Photo OCR via a vision-capable model; runs as a background job, UI shows progress |
| `offer_meditation` | Companion's tool to propose a session; triggers the router and an approval interrupt | User can change tradition, approach and length before confirming |
| `render_audio` | Splits the script on `[pause Ns]`, sends each spoken segment to ElevenLabs with the pack's `voice_id`, caches by hash, uploads to R2 | Silence is inserted by the player, not generated |
| `pick_image` | Chooses from `image_library` by tradition, theme and time of day; occasionally generates a fresh one | Abstract imagery only: light, nature, geometry; no deities or figures |
| `get_practice_history` | Returns recent sessions and notes for the companion | Read-only |

**ElevenLabs (voices):** per-character billing, and silence is not billed ([ElevenLabs pricing explainer](https://dev.to/techsifted/elevenlabs-pricing-2026-plans-credits-and-api-costs-explained-1549)). Their API page lists Flash/Turbo at $0.04 per 1K characters ([ElevenLabs API pricing](https://elevenlabs.io/pricing/api)); third-party summaries list Multilingual v2 and v3 at $0.10 per 1K ([ModelsLab](https://modelslab.com/elevenlabs-api-pricing)). Estimate: a 10-minute script is 4,000–6,000 characters, roughly $0.20–$0.60 per session. Use v3 for quality; fall back to Flash for drafts and tests. The free tier is not licensed for commercial use, so testers beyond Sanjay need a paid plan.

**Nano Banana (images):** Nano Banana 2.1 is generally available on the Gemini API at about 3.4¢ per 1K image ([FourWeekMBA](https://fourweekmba.com/ai-google-halves-nano-banana-image-price-triples-input-price/)); confirm the current model ID in Google's docs before coding. Pre-generate a library of about 5 traditions × 6 themes × 3 times of day (90 images, under $5), then add fresh images sparingly.

**LLMs:** Claude Sonnet 5.5 for `companion`, `guide` and `reflect` (the voice of the app, where writing quality matters most); Claude Haiku 5.5 for `guard`, `router` and `summarize`; Gemini for images (Nano Banana), embeddings and photo OCR. Published rates: Sonnet 5.5 at $2 / $10 and Haiku 5.5 at $0.10 / $0.50 per million input / output tokens for prompts up to 100K ([Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)); Gemini 3.x Flash at $0.75 / $3.75 through Dec 31, 2026, then $1.50 / $7.50 ([Google Cloud pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)). At one daily user, all model calls together are roughly $5 a month on Claude or $2–$4 on Gemini Flash (estimate), so quality decides. Milestone 5 includes a blind bake-off: the same 5 briefs per tradition written by Sonnet 5.5 and Gemini Flash, rated by Sanjay without labels; the winner becomes the `guide` default. Every node's provider and model is a config value.

**Audio playback (browser):** Web Audio API plays segments in sequence with timed silences and loops an ambient bed underneath, with a volume slider for each. No server-side ffmpeg.

## Safety, privacy and the Hold

Safety handling and journal privacy ship in v0, before anyone but Sanjay uses the app; they are not later hardening.

**Crisis handling**

- `guard` runs on every chat message and every uploaded entry, including bulk imports.
- On `crisis`: no meditation is offered; the response is warm, plain, and points to the 988 Suicide & Crisis Lifeline (call or text 988 in the US) plus an international directory link; the companion stays present in the conversation.
- On `concern`: the companion checks in gently before offering anything.
- Flags are stored as a boolean on the session, never the text, and are never used for analytics.
- `evals/safety/` holds test messages that must route correctly; CI fails if any regress.

**Privacy (the Hold)**

- Journal text is encrypted at the application layer; `journal_chunks` in the store hold embeddings plus an entry reference, and chunk text is decrypted only at retrieval time.
- No journal content is used for model training or shared beyond the model APIs that process it; use API settings with no data retention where the provider offers them.
- LangSmith tracing is off in production; locally, journal content is redacted from traces.
- Users can export the Hold (Markdown/JSON) and delete their account and all data in one action.
- A plain-language privacy page states all of the above before any tester signs up.

**Tradition integrity**

- Guides never speak as founders, deities or figures, and never claim scriptural authority for generated text.
- Quotations come only from `sources/` with attribution; no invented quotes.
- Images stay abstract; no depictions of deities, prophets or saints.

## Hosting, deployment and cost

The app moves off AWS to four inexpensive pieces: SvelteKit on Vercel, one small VPS for the Python backend, Supabase, and Cloudflare R2. Fixed costs should land in the low tens of dollars a month; usage costs (voices, models) dominate.

| Piece | Runs | Host | Notes |
| --- | --- | --- | --- |
| Frontend | SvelteKit, Tailwind, Lato | Vercel (Hobby while non-commercial) or Cloudflare Pages | Domain `grove.substep.co`; `thegrove.substep.co` redirects |
| Backend | FastAPI + LangGraph + background worker | One small VPS (Hetzner, or Fly.io if managed is preferred), Docker Compose, Caddy for TLS | `api.grove.substep.co`; worker handles uploads, rendering, summaries |
| Database and auth | Postgres + pgvector, magic-link auth | Supabase | Free tier pauses idle projects; move to paid once testers join |
| Storage | Audio segments, images, uploads | Cloudflare R2 | No egress fees; signed URLs only |
| DNS | substep.co zone | Cloudflare (existing) |  |
| CI/CD | Lint, tests, safety evals, deploy | GitHub Actions | Frontend auto-deploys from Vercel; backend deploys by SSH + `docker compose pull` |

**Approximate monthly cost for Sanjay's daily use** (estimates, not quotes): VPS a few dollars to about $10; ElevenLabs about $6–$18 at 30 sessions; model calls about $5; R2 and Supabase free tiers at this scale; images a one-time \~$5 for the library.

## Local development setup

The whole app runs on a laptop with one command and **boots with zero external API keys**: every outside service has a mock or local adapter, so Claude Code can build and test milestones 1–4 before any keys exist. Real keys are added to `.env` files later, one service at a time.

**Prerequisites:** Docker Desktop, Node 22 + pnpm, Python 3.12 + uv, Supabase CLI, Claude Code (CLI or VS Code), and optionally the Claude in Chrome extension for browser testing.

**One command:** `make dev` starts everything; `make check` runs the full verification suite.

| Service | Local form | Address |
| --- | --- | --- |
| Postgres + pgvector + auth | `supabase start` (Docker) | API `127.0.0.1:54321`, DB `:54322`, Studio `:54323` |
| Backend | `uv run fastapi dev` | `localhost:8000` |
| Worker | `uv run python -m app.worker` | (background) |
| Frontend | `pnpm dev` | `localhost:5173` |
| Magic-link emails | Supabase's local mail catcher (shown in `supabase status`) | browser |
| Media storage | Local disk adapter (`./.data/media`) | served by the backend |

**Adapters (switch by env var, no code changes):**

| Concern | Local default | Real |
| --- | --- | --- |
| Main and fast LLMs | `mock` (deterministic canned replies) when no key is set | Anthropic / Google per config |
| Embeddings | `mock` (hash-based vectors, same dimensions) | Gemini embeddings |
| Text-to-speech | `TTS_MODE=mock` (silent placeholder audio of the right length) | `flash` for dev runs, `v3` for real sessions |
| Images | `IMAGE_MODE=placeholder` (gradient SVGs per tradition) | `library`, then `generate` |
| Storage | `STORAGE_BACKEND=local` | `r2` |
| OCR (photo journals) | `mock` | Gemini vision |

**Environment files** (commit the `.example` versions only; real `.env` files are gitignored):

```bash
# api/.env.example
APP_ENV=local
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_SERVICE_ROLE_KEY=        # printed by `supabase start`
SUPABASE_JWT_SECRET=              # printed by `supabase start`
JOURNAL_ENCRYPTION_KEY=           # generate with: uv run python -m app.scripts.genkey

LLM_PROVIDER_MAIN=mock            # mock | anthropic | google
LLM_MODEL_MAIN=claude-sonnet-5-5
LLM_PROVIDER_FAST=mock
LLM_MODEL_FAST=claude-haiku-5-5
EMBEDDING_PROVIDER=mock           # mock | google
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=                   # Gemini: images, embeddings, OCR, LLM fallback

ELEVENLABS_API_KEY=
TTS_MODE=mock                     # mock | flash | v3
IMAGE_MODE=placeholder            # placeholder | library | generate
STORAGE_BACKEND=local             # local | r2
LOCAL_STORAGE_DIR=./.data/media
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=grove-media

LANGSMITH_TRACING=false
```

```bash
# web/.env.example
PUBLIC_API_URL=http://localhost:8000
PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
PUBLIC_SUPABASE_ANON_KEY=         # printed by `supabase start`
```

**Seed data:** `make seed` creates a test user, three default-tradition profiles, and a set of clearly synthetic journal entries (never real entries) so memory and recall can be tested.

**Verification loop for Claude Code:**

- `make check` = lint + type check + pytest + Vitest + safety evals + tradition evals (mock mode).
- A Stop hook in `.claude/settings.json` runs `make check` so a turn cannot end with a failing suite.
- For UI work, run Claude Code with `--chrome` and ask it to walk the flow at `localhost:5173` and read console errors.
- `make check-live` re-runs the tradition evals against real models and voices; run it manually, since it costs money.

**Adding keys later:** paste a key into `api/.env`, flip that service's mode (e.g. `LLM_PROVIDER_MAIN=anthropic`), and restart. Keys never go into the Claude Code chat or into committed files; a permission rule denies Claude reads of `.env` (it reads `.env.example` instead).

## Repo structure and CLAUDE.md

One monorepo, `substep/grove`, with the frontend, backend and tradition packs side by side so Claude Code sees the whole system. Export this doc to Markdown as `docs/SPEC.md`, and commit the CLAUDE.md below at the repo root.

```markdown
grove/
  CLAUDE.md
  docs/SPEC.md                 # this document
  web/                         # SvelteKit app
    src/routes/                # /, /session, /hold, /settings, /onboarding
    src/lib/audio/             # Web Audio player: segments, pauses, ambient bed
    src/lib/api.ts             # typed client for the FastAPI backend, SSE streaming
  api/                         # Python backend
    app/main.py                # FastAPI: auth check, chat SSE, uploads, sessions
    app/graph/                 # LangGraph: state.py, graph.py, nodes/*.py
    app/tools/                 # upload_journal, render_audio, pick_image, history
    app/memory/                # store namespaces, summarizer, encryption helpers
    app/worker.py              # background jobs
    tests/  evals/safety/  evals/traditions/
  traditions/                  # skill packs (content, not code)
    mindfulness/ buddhist/ christian/ yogic/ raja-yoga/
  supabase/migrations/         # SQL: tables, RLS, pgvector
  infra/                       # docker-compose.yml, Caddyfile, deploy workflow
```

```markdown
# CLAUDE.md — The Grove

The Grove (grove.substep.co) is a private daily companion: chat or journal, then a
tradition-specific guided meditation. Full spec: docs/SPEC.md. Read it before large changes.

## Stack
- web/: SvelteKit + TypeScript + Tailwind. Font Lato. Deployed on Vercel.
- api/: Python 3.12, FastAPI, LangGraph, LangChain chat models. Managed with uv.
- Supabase Postgres + pgvector; LangGraph PostgresSaver (threads) and PostgresStore (memory).
- Cloudflare R2 for audio/images. ElevenLabs for voices. Claude (Sonnet 5.5 / Haiku 5.5) for text; Gemini for images, embeddings, OCR.

## Rules
- Traditions are content: never hard-code tradition logic in Python; read traditions/<id>/.
- Guides never speak as founders, deities or religious figures. No invented quotations.
- Journal text is always encrypted before insert; never log it, never send it to tracing.
- Every user-facing input passes through the guard node first. Do not bypass it.
- No streaks, badges or push-notification nudges.
- Model choice lives in config (api/app/config.py), never inline in nodes.

## Commands
- web: pnpm dev | pnpm test | pnpm lint
- api: uv run fastapi dev | uv run pytest | uv run python -m evals.safety
- db: supabase db push

## Working style
- Work milestone by milestone (docs/SPEC.md, Build milestones). Finish and test one before starting the next.
- Ask before adding a dependency or changing the data model.
- After each milestone, update the checklist in docs/SPEC.md.
```

## Build milestones

Eight milestones, each small enough for one or two Claude Code sessions and each ending in something Sanjay can use. Start every milestone with: "Read CLAUDE.md and docs/SPEC.md, then implement milestone N."

| # | Milestone | Done when |
| --- | --- | --- |
| 1 | **Scaffold** — monorepo, SvelteKit app, FastAPI app, local Supabase with migrations and RLS, mock adapters, .env.example, make dev / make check, CI | `pnpm dev` and `uv run fastapi dev` run locally; magic-link sign-in works; CI is green |
| 2 | **Companion chat** — LangGraph with `guard` and `companion`, PostgresSaver threads, SSE streaming to the UI | A streamed conversation persists across reloads; safety evals route crisis messages correctly |
| 3 | **Memory** — PostgresStore namespaces, onboarding sets default tradition, background `summarize` | The companion recalls the default tradition and a theme from an earlier session |
| 4 | **The Hold** — encrypted journal entries, paste and file upload (.txt, .md, .pdf, Day One JSON), chunking and embedding, history view | An uploaded month of entries is listed in the Hold and recalled in chat; nothing plaintext in the database |
| 5 | **Meditation script** — `offer_meditation`, approval interrupt, `router`, `guide` subgraph, `raja-yoga` and `mindfulness` packs | A confirmed offer produces a script with pause markers that passes the pack's evals |
| 6 | **Audio** — `render_audio` with ElevenLabs, hash cache, R2, Web Audio player with ambient bed | A 10-minute session plays end to end on a phone browser with correct pauses |
| 7 | **Imagery and remaining packs** — image library generation script, `pick_image`, `buddhist`, `christian`, `yogic` packs | Each tradition plays with its own voice and image |
| 8 | **Deploy and dogfood** — VPS, Caddy, `grove.substep.co`, privacy page, export and delete | Sanjay uses it daily; a 30-day log of what to fix lives in `docs/dogfood.md` |

Checklist for Claude Code to tick off:

- [x] 1\. Scaffold
- [x] 2\. Companion chat
- [ ] 3\. Memory
- [ ] 4\. The Hold
- [ ] 5\. Meditation script
- [ ] 6\. Audio
- [ ] 7\. Imagery and remaining packs
- [ ] 8\. Deploy and dogfood

## Open questions

- [ ] Pick the five ElevenLabs voices (one per launch tradition) from the voice library; record `voice_id`s in each `pack.yaml`.
- [ ] Choose the default frontier model (Gemini vs Claude) after comparing script quality on the `raja-yoga` evals.
- [ ] Who reviews the `buddhist`, `christian` and `yogic` packs before testers use them?
- [ ] Which BK sources (Murli excerpts, practice notes) are appropriate to include in `raja-yoga/sources/`, and with what attribution?
- [ ] Ambient beds: license a small set or generate them (ElevenLabs sound effects / music)?
- [ ] Trademark and app-store check on "The Grove" before any public launch.
- [ ] Day One export format: confirm the current JSON schema with a real export.

## Sources

- [Letta — Our next phase](https://letta.com/blog/our-next-phase)
- [LangChain docs — Long-term memory (PostgresStore)](https://docs.langchain.com/oss/python/langchain/long-term-memory)
- [LangChain blog — Semantic search for LangGraph memory](https://www.langchain.com/blog/semantic-search-for-langgraph-memory)
- [ElevenLabs — API pricing](https://elevenlabs.io/pricing/api)
- [ModelsLab — ElevenLabs API pricing 2026](https://modelslab.com/elevenlabs-api-pricing)
- [TechSifted via DEV — ElevenLabs pricing explained](https://dev.to/techsifted/elevenlabs-pricing-2026-plans-credits-and-api-costs-explained-1549)
- [FourWeekMBA — Nano Banana 2.1 pricing](https://fourweekmba.com/ai-google-halves-nano-banana-image-price-triples-input-price/)
