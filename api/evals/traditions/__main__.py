"""Tradition evals: run each pack's evals.md prompts through the guide (mock mode by default).

Packs load and validate now (M3). evals.md files and the guide subgraph arrive in M5; until
then, packs without evals.md are reported and skipped, never counted as passing.
"""

import sys

from app.config import Settings
from app.traditions import PackError, load_packs


def main() -> int:
    root = Settings(checkpointer_backend="memory").traditions_dir
    try:
        packs = load_packs(root)
    except PackError as exc:
        print(f"tradition evals: invalid pack: {exc}")
        return 1
    with_evals = [pid for pid in packs if (root / pid / "evals.md").exists()]
    print(
        f"tradition evals: {len(packs)} packs valid; "
        f"{len(with_evals)} with evals.md (guide and evals arrive in M5)"
    )
    if with_evals:
        print("tradition evals: evals.md found but the guide is not implemented yet")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
