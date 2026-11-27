"""Print a new random JOURNAL_ENCRYPTION_KEY (base64, 32 bytes). Paste it into api/.env."""

import base64
import secrets


def main() -> None:
    print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())


if __name__ == "__main__":
    main()
