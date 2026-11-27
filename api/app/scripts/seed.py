"""Seed local Supabase with synthetic test users, profiles and journal entries.

Every entry here is clearly synthetic. Never put real journal text in seed data.

Journal bodies are written as placeholder bytes until M4 adds application-layer
encryption; the column is bytea, so no plaintext column exists either way.
"""

import sys
from datetime import date, timedelta

import httpx
import psycopg

from app.config import get_settings

PASSWORD = "grove-local-only"  # noqa: S105 - local seed users only
USERS = [
    ("test@grove.local", "Test User", "mindfulness"),
    ("raja@grove.local", "Raja Tester", "raja-yoga"),
    ("buddhist@grove.local", "Buddhist Tester", "buddhist"),
]
SYNTHETIC_ENTRIES = [
    "[SYNTHETIC] Slept badly, work deadline looming, felt scattered all morning.",
    "[SYNTHETIC] Walked by the river after lunch. Calmer. Grateful for the light.",
    "[SYNTHETIC] Argued with a friend, then apologised. Still thinking about it.",
]
# Placeholder until M4: real entries go through app.memory encryption helpers.
PLACEHOLDER_CIPHERTEXT_PREFIX = b"seed-synthetic:"


def ensure_user(client: httpx.Client, base: str, email: str) -> str:
    resp = client.post(
        f"{base}/auth/v1/admin/users",
        json={"email": email, "password": PASSWORD, "email_confirm": True},
    )
    if resp.status_code < 300:
        return str(resp.json()["id"])
    listing = client.get(f"{base}/auth/v1/admin/users", params={"per_page": 1000})
    listing.raise_for_status()
    for user in listing.json()["users"]:
        if user["email"] == email:
            return str(user["id"])
    resp.raise_for_status()
    raise RuntimeError(f"could not create or find {email}")


def main() -> int:
    s = get_settings()
    if not s.supabase_service_role_key:
        print("SUPABASE_SERVICE_ROLE_KEY is empty in api/.env (see `supabase status`).")
        return 1
    headers = {
        "apikey": s.supabase_service_role_key,
        "Authorization": f"Bearer {s.supabase_service_role_key}",
    }
    with (
        httpx.Client(headers=headers, timeout=10) as client,
        psycopg.connect(s.database_url) as conn,
    ):
        for email, name, tradition in USERS:
            user_id = ensure_user(client, s.supabase_url, email)
            conn.execute(
                """insert into public.profiles (user_id, display_name, default_tradition, timezone)
                   values (%s, %s, %s, 'America/New_York')
                   on conflict (user_id) do update
                   set display_name = excluded.display_name,
                       default_tradition = excluded.default_tradition""",
                (user_id, name, tradition),
            )
            conn.execute(
                "delete from public.journal_entries where user_id = %s and source = 'paste'",
                (user_id,),
            )
            for i, text in enumerate(SYNTHETIC_ENTRIES):
                conn.execute(
                    "insert into public.journal_entries"
                    " (user_id, source, body_encrypted, entry_date)"
                    " values (%s, 'paste', %s, %s)",
                    (
                        user_id,
                        PLACEHOLDER_CIPHERTEXT_PREFIX + str(len(text)).encode(),
                        date.today() - timedelta(days=i),
                    ),
                )
            print(f"seeded {email} ({tradition})")
    print(f"done. local password for all seed users: {PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
