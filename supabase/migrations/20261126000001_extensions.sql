-- Extensions: pgvector for the LangGraph store's semantic index, pgcrypto for gen_random_uuid().
create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto with schema extensions;
