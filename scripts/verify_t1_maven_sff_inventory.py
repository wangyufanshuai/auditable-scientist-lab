"""Verify a post-hoc, source-pinned inventory of nearby MAVEN SFF files."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/T1_MAVEN_SFF_EXPLORATORY_INVENTORY.json"
DIRECTORY = ROOT / "data/references/maven_sff"
AUDIT = ROOT / "artifacts/t1-maven-sff-exploratory-audit.json"


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.names: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.names.add(dict(attrs).get("href") or "")


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _records(path: Path) -> list[list[str]]:
    with path.open(encoding="ascii", newline="") as stream:
        records = [row for row in csv.reader(stream) if len(row) > 1 and row[1].strip() == "R"]
    if not records or any(len(row) != 43 for row in records):
        raise ValueError(f"SFF R-row shape differs: {path.name}")
    if [int(row[0]) for row in records] != list(range(1, len(records)+1)):
        raise ValueError(f"SFF R-row numbering differs: {path.name}")
    return records


def evaluate() -> dict:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    if (inventory.get("status") != "posthoc-source-discovery-not-preregistered"
            or inventory.get("known_limits") != {
                "field_units_and_frame_verified": False, "time_scale_verified": False,
                "SFF_SIS_available": False, "complete_cruise_force_history_verified": False,
                "values_admitted_to_dynamics_model": False, "independent_observables": False,
                "scientific_holdout": False, "mission_validation": False,
                "claim_status": "unverified"}):
        raise ValueError("SFF inventory boundary differs")
    index = DIRECTORY / "index.html"
    if _hash(index) != inventory["source_index_sha256"]:
        raise ValueError("SFF source directory index differs")
    links = _Links()
    links.feed(index.read_text(encoding="utf-8", errors="replace"))
    rows: list[dict] = []
    records_by_name: dict[str, list[list[str]]] = {}
    for filename, size, digest in inventory["files"]:
        if filename not in links.names or "/" in filename or "\\" in filename:
            raise ValueError(f"SFF filename absent from official index: {filename}")
        path = DIRECTORY / filename
        if path.stat().st_size != size or _hash(path) != digest:
            raise ValueError(f"SFF source bytes differ: {filename}")
        records = _records(path)
        records_by_name[filename] = records
        rows.append({"filename": filename, "bytes": size, "sha256": digest,
                     "record_count": len(records),
                     "first_raw_start": min(row[3].strip() for row in records),
                     "last_raw_end": max(row[4].strip() for row in records)})
    pairs = [(0, 1), (2, 3), (4, 5), (6, 7)]
    duplicate_pairs = []
    for left, right in pairs:
        a, b = inventory["files"][left][0], inventory["files"][right][0]
        first, second = records_by_name[a], records_by_name[b]
        same_except_production = len(first) == len(second) and all(
            x[:2]+x[3:] == y[:2]+y[3:] for x, y in zip(first, second, strict=True))
        if not same_except_production or first == second:
            raise ValueError(f"SFF duplicate record relationship differs: {a}, {b}")
        duplicate_pairs.append([a, b])
    return {"schema_version": "t1-maven-sff-exploratory-audit-v1",
            "status": "verified-local-source-inventory-only",
            "inventory_sha256": _hash(INVENTORY),
            "index_sha256": inventory["source_index_sha256"],
            "source_directory_url": inventory["source_directory_url"],
            "files": rows, "same_records_except_production_time": duplicate_pairs,
            "boundaries": inventory["known_limits"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    audit = evaluate()
    if args.write:
        audit["recorded_at"] = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(audit, indent=2, sort_keys=True)+"\n"
        if AUDIT.exists() and AUDIT.read_text(encoding="utf-8") != payload:
            raise ValueError("refusing to overwrite different SFF inventory audit")
        AUDIT.write_text(payload, encoding="utf-8", newline="\n")
    else:
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        timestamp = saved.pop("recorded_at", None)
        if (not isinstance(timestamp, str)
                or datetime.fromisoformat(timestamp.replace("Z", "+00:00")).tzinfo is None
                or saved != audit):
            raise ValueError("saved SFF inventory audit differs from local sources")
    print(json.dumps({"status": audit["status"], "files": len(audit["files"]),
                      "duplicate_pairs": len(audit["same_records_except_production_time"])},
                     sort_keys=True))


if __name__ == "__main__":
    main()
