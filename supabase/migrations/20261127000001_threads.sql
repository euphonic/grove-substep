-- M2: conversation threads and a private schema for LangGraph's checkpointer.

-- One row per conversation. The id is the LangGraph thread_id.
create table public.threads (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users (id) on delete cascade,
  -- No title column on purpose: deriving one from chat would store message text in plaintext.
  -- Set when the guard flags crisis in this thread. Boolean only: never the text,
  -- never used for analytics.
  safety_flagged  boolean not null default false,
  created_at      timestamptz not null default now(),
  last_message_at timestamptz not null default now()
);
create index threads_user_recent_idx on public.threads (user_id, last_message_at desc);

alter table public.threads enable row level security;
revoke all on public.threads from anon;
grant select, insert, update, delete on public.threads to authenticated;

create policy threads_select_own on public.threads for select to authenticated
  using ((select auth.uid()) = user_id);
create policy threads_insert_own on public.threads for insert to authenticated
  with check ((select auth.uid()) = user_id);
create policy threads_update_own on public.threads for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy threads_delete_own on public.threads for delete to authenticated
  using ((select auth.uid()) = user_id);

-- LangGraph's PostgresSaver creates its tables (checkpoints, checkpoint_blobs, ...) with
-- unqualified names. The API points it at this schema via search_path, so conversation
-- state is never in `public` and never reachable through the Supabase REST API.
create schema if not exists langgraph;
revoke all on schema langgraph from public, anon, authenticated;
alter default privileges in schema langgraph revoke all on tables from public, anon, authenticated;
