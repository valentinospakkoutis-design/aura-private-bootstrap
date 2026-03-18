from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.live_readiness import LiveReadinessChecker, exit_code_for_verdict, render_text_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AURA live readiness auto-check")
    parser.add_argument("--json", action="store_true", dest="json_mode", help="Print machine-readable JSON output")
    args = parser.parse_args(argv)

    checker = LiveReadinessChecker(backend_root=BACKEND_ROOT)
    report = checker.run()

    if args.json_mode:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_text_report(report))

    return exit_code_for_verdict(report.verdict)


if __name__ == "__main__":
    raise SystemExit(main())
