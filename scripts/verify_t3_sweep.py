"""Recompute the bounded T3 oscillator step-size and parameter sweep."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from auditable_scientist.tracks.convergence import build_receipt, verify_saved_receipt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/t3-sweep.json"
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the current sweep audit")
    parser.add_argument("--verify", action="store_true", help="verify the committed sweep audit")
    args = parser.parse_args()
    if args.write == args.verify:
        parser.error("choose exactly one of --write or --verify")
    if args.write:
        result = build_receipt()
        if not result["passed"]:
            raise SystemExit(f"T3 bounded sweep failed: {result['checks']}")
        result["recorded_at"] = datetime.now(timezone.utc).isoformat()
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    else:
        result = verify_saved_receipt(OUTPUT)
    print(json.dumps({"passed": result["passed"], "checks": result["checks"], "summary": result["summary"]}, indent=2))


if __name__ == "__main__":
    main()
