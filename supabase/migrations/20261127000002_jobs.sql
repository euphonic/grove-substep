-- M3: background job queue, processed by the worker (app/worker.py).
-- Payloads carry ids only (user_id, thread_id, ...): never message or journal text.

create table public.jobs (
  id         bigint generated always as identity primary key,
  kind       text not null,
  payload    jsonb not null default '{}',
  -- For debouncing: at most one queued job per dedupe_key (e.g. 'summarize:<thread_id>').
  dedupe_key text,
  status     text not null default 'queued'
               check (status in ('queued', 'running', 'done', 'failed')),
  attempts   smallint not null default 0,
  run_after  timestamptz not null default now(),
  locked_at  timestamptz,
  -- Error type only (e.g. 'TimeoutError'), never a message that could contain user text.
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index jobs_ready_idx on public.jobs (run_after) where status = 'queued';
create unique index jobs_dedupe_queued_idx on public.jobs (dedupe_key)
  where status = 'queued' and dedupe_key is not null;

-- Server-only: RLS on with no policies, and no grants to client roles.
alter table public.jobs enable row level security;
revoke all on public.jobs from anon, authenticated;
