"""Safety evals: every case must route to its expected guard label.

Cases live in evals/safety/cases.json as [{"text": ..., "expect": "ok|concern|crisis"}].
The guard node arrives in M2; until then the runner reports 0 cases and never fakes a pass.
"""

import json
import sys
from pathlib import Path

CASES = Path(__file__).with_name("cases.json")


def main() -> int:
    cases = json.loads(CASES.read_text()) if CASES.exists() else []
    if not cases:
        print("safety evals: 0 cases (guard node not implemented until M2)")
        return 0
    print(f"safety evals: {len(cases)} cases defined but no guard to run them against")
    return 1


if __name__ == "__main__":
    sys.exit(main())
