-- Row-level security: every app table is locked down; users see only their own rows.

alter table public.profiles        enable row level security;
alter table public.journal_entries enable row level security;
alter table public.sessions        enable row level security;
alter table public.uploads         enable row level security;
alter table public.image_library   enable row level security;
alter table public.audio_cache     enable row level security;

-- Anonymous users get nothing anywhere.
revoke all on public.profiles, public.journal_entries, public.sessions, public.uploads,
  public.image_library, public.audio_cache from anon;

-- User-owned tables: full CRUD on own rows only.
grant select, insert, update, delete
  on public.profiles, public.journal_entries, public.sessions, public.uploads to authenticated;

do $$
declare t text;
begin
  foreach t in array array['profiles', 'journal_entries', 'sessions', 'uploads'] loop
    execute format(
      'create policy %1$I on public.%2$I for select to authenticated using ((select auth.uid()) = user_id)',
      t || '_select_own', t);
    execute format(
      'create policy %1$I on public.%2$I for insert to authenticated with check ((select auth.uid()) = user_id)',
      t || '_insert_own', t);
    execute format(
      'create policy %1$I on public.%2$I for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id)',
      t || '_update_own', t);
    execute format(
      'create policy %1$I on public.%2$I for delete to authenticated using ((select auth.uid()) = user_id)',
      t || '_delete_own', t);
  end loop;
end $$;

-- Image library: readable by signed-in users, written only by the service role.
revoke all on public.image_library from authenticated;
grant select on public.image_library to authenticated;
create policy image_library_read on public.image_library for select to authenticated using (true);

-- Audio cache: service role only (no grants, no policies for anon/authenticated).
revoke all on public.audio_cache from authenticated;
