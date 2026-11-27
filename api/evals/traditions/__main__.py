"""Tradition evals: run each pack's evals.md prompts through the guide (mock mode by default).

Packs and the guide subgraph arrive in M5; until then the runner reports what it found.
"""

import sys

from app.config import get_settings


def main() -> int:
    root = get_settings().traditions_dir
    packs = sorted(p.name for p in root.iterdir() if (p / "pack.yaml").exists())
    if not packs:
        print("tradition evals: 0 packs with pack.yaml (packs arrive in M5)")
        return 0
    print(f"tradition evals: found packs {packs} but the guide is not implemented yet")
    return 1


if __name__ == "__main__":
    sys.exit(main())
