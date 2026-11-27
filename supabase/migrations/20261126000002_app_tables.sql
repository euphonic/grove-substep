-- App tables (docs/SPEC.md, Memory and data model).
-- Traditions are content (traditions/<id>/), so tradition columns are plain text, not enums or FKs.
-- LangGraph checkpointer/store tables are created by PostgresSaver/PostgresStore.setup() in M2/M3.

create table public.profiles (
  user_id           uuid primary key references auth.users (id) on delete cascade,
  display_name      text,
  default_tradition text,
  timezone          text not null default 'UTC',
  created_at        timestamptz not null default now()
);

-- The Hold. Bodies are encrypted in the application before insert; there is no plaintext column.
create table public.journal_entries (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users (id) on delete cascade,
  source         text not null
                   check (source in ('chat', 'paste', 'file', 'photo', 'dayone', 'reflection')),
  body_encrypted bytea not null,
  entry_date     date not null default current_date,
  created_at     timestamptz not null default now()
);
create index journal_entries_user_date_idx on public.journal_entries (user_id, entry_date desc);

create table public.sessions (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users (id) on delete cascade,
  thread_id      text,
  tradition      text not null,
  approach       text not null,
  minutes        smallint not null check (minutes between 1 and 60),
  intent         text,
  script         text,
  audio_keys     text[] not null default '{}',
  image_key      text,
  -- Crisis/concern flag from the guard node. Boolean only: never the text, never used for analytics.
  safety_flagged boolean not null default false,
  completed_at   timestamptz,
  rating         smallint check (rating between 1 and 5),
  created_at     timestamptz not null default now()
);
create index sessions_user_created_idx on public.sessions (user_id, created_at desc);

create table public.uploads (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  filename   text not null,
  mime       text not null,
  status     text not null default 'pending'
               check (status in ('pending', 'processing', 'done', 'failed')),
  entry_ids  uuid[] not null default '{}',
  created_at timestamptz not null default now()
);
create index uploads_user_created_idx on public.uploads (user_id, created_at desc);

-- Shared, non-personal content.
create table public.image_library (
  id          uuid primary key default gen_random_uuid(),
  tradition   text not null,
  theme       text not null,
  time_of_day text not null check (time_of_day in ('morning', 'afternoon', 'evening', 'night')),
  storage_key text not null unique,
  created_at  timestamptz not null default now()
);
create index image_library_lookup_idx on public.image_library (tradition, theme, time_of_day);

-- TTS cache keyed by hash(voice + segment text). Server-only.
create table public.audio_cache (
  hash        text primary key,
  storage_key text not null,
  created_at  timestamptz not null default now()
);
