"""Inspect a pinned PDS MAVEN operations-event catalog at frozen NAV arcs."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from hashlib import md5, sha256
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/T1_MAVEN_OPS_EVENT_SEARCH_PROTOCOL.json"
PROTOCOL_SHA256 = "07f7dcc05063d1102835fc1d8549bb776b8c2b6f1ee3dce12f31060e919aee33"
PREREGISTRATION_COMMIT = "5c1ad36"
DATA_DIR = ROOT / "data/references/maven_anc_events"
STEM = "ops_events_2013-01-01-00-00-00_2021-11-15-00-00-00"
LABEL = DATA_DIR / f"{STEM}.xml"
CSV = DATA_DIR / f"{STEM}.csv"
AUDIT = ROOT / "artifacts/t1-maven-ops-event-search-audit.json"
FIELDS = ("id", "event_type_id", "start_time", "end_time", "source",
          "description", "discussion")
PATTERNS = {
    "desat": re.compile(r"desat", re.IGNORECASE),
    "angular momentum": re.compile(r"angular momentum", re.IGNORECASE),
    "reaction wheel": re.compile(r"reaction wheel", re.IGNORECASE),
    "thruster": re.compile(r"thruster", re.IGNORECASE),
    "maneuver": re.compile(r"maneuver", re.IGNORECASE),
    "tcm": re.compile(r"\btcm\b", re.IGNORECASE),
    "amd": re.compile(r"\bamd\b", re.IGNORECASE),
    "momentum dump": re.compile(r"momentum dump", re.IGNORECASE),
}


def _sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _source(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(),
            "sha256": _sha(path), "bytes": path.stat().st_size}


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("MAVEN event timestamp lacks a timezone")
    return parsed


def _overlap(start: datetime, end: datetime,
             window_start: datetime, window_end: datetime) -> bool:
    return start < window_end and end >= window_start


def _row_ref(row: dict[str, str], terms: list[str]) -> dict:
    return {"id": row["id"], "event_type_id": row["event_type_id"],
            "start_time": row["start_time"], "end_time": row["end_time"],
            "source": row["source"], "matched_terms": terms,
            "row_sha256": sha256(json.dumps(row, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()}


def evaluate() -> dict:
    if _sha(PROTOCOL) != PROTOCOL_SHA256:
        raise ValueError("precommitted MAVEN event-search protocol differs")
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if (protocol["schema_version"] != "t1-maven-ops-event-search-protocol-v1"
            or protocol["admission_gates"]["claim_status"] != "unverified"
            or protocol["search_contract"]["case_insensitive_terms"] != list(PATTERNS)
            or protocol["search_contract"]["fields_to_search"] !=
            ["event_type_id", "description", "discussion"]):
        raise ValueError("MAVEN event-search protocol semantics differ")
    source = protocol["source"]
    if _sha(LABEL) != source["label_sha256"]:
        raise ValueError("PDS MAVEN event label differs")
    label = ET.parse(LABEL).getroot()
    find = lambda name: label.findtext(f".//{{*}}{name}")
    if (find("logical_identifier")+"::"+find("version_id") != source["product_lidvid"]
            or find("file_name") != CSV.name
            or int(find("file_size")) != source["data_bytes_from_label"]
            or find("md5_checksum") != source["data_md5_from_label"]
            or int(find("records")) != source["records_from_label"]):
        raise ValueError("PDS MAVEN event product label contract differs")
    if CSV.stat().st_size != source["data_bytes_from_label"]:
        raise ValueError("PDS MAVEN event CSV byte count differs")
    md = md5(usedforsecurity=False)
    with CSV.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            md.update(chunk)
    if md.hexdigest() != source["data_md5_from_label"]:
        raise ValueError("PDS MAVEN event CSV MD5 differs")
    arcs = []
    for item in protocol["frozen_arcs"]:
        start, end = _datetime(item["start_utc"]), _datetime(item["end_utc"])
        context = timedelta(days=protocol["search_contract"]["context_days_each_side"])
        arcs.append({"start_et_tdb_seconds": item["start_et_tdb_seconds"],
                     "start_utc": item["start_utc"], "end_utc": item["end_utc"],
                     "all_arc_events": 0, "keyword_arc_hits": [],
                     "keyword_context_hits": [], "_window": (start, end),
                     "_context": (start-context, end+context)})
    row_count = 0
    event_ids: set[str] = set()
    with CSV.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("PDS MAVEN event CSV columns differ")
        for row in reader:
            row_count += 1
            if not row["id"] or row["id"] in event_ids or None in row:
                raise ValueError("PDS MAVEN event ID or row shape differs")
            event_ids.add(row["id"])
            start = _datetime(row["start_time"])
            end = _datetime(row["end_time"] or row["start_time"])
            if end < start:
                raise ValueError("PDS MAVEN event interval is inverted")
            searchable = "\n".join(row[field] for field in
                                   protocol["search_contract"]["fields_to_search"])
            terms = [term for term, pattern in PATTERNS.items() if pattern.search(searchable)]
            for arc in arcs:
                if _overlap(start, end, *arc["_window"]):
                    arc["all_arc_events"] += 1
                    if terms:
                        arc["keyword_arc_hits"].append(_row_ref(row, terms))
                if terms and _overlap(start, end, *arc["_context"]):
                    arc["keyword_context_hits"].append(_row_ref(row, terms))
    if row_count != source["records_from_label"]:
        raise ValueError("PDS MAVEN event record count differs")
    for arc in arcs:
        del arc["_window"]
        del arc["_context"]
    return {
        "schema_version": "t1-maven-ops-event-search-audit-v1",
        "status": "catalog-inspected-not-mission-validation",
        "protocol_sha256": PROTOCOL_SHA256,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "product_lidvid": source["product_lidvid"],
        "source_files": [_source(path) for path in (PROTOCOL, Path(__file__).resolve(), LABEL, CSV)],
        "records_checked": row_count,
        "arcs": arcs,
        "boundaries": {"catalog_scope_only": True, "event_list_complete_for_desats": False,
                       "impulse_vectors_admitted": False, "independent_observables": False,
                       "scientific_holdout": False, "mission_validation": False,
                       "claim_status": "unverified"},
    }


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
            raise ValueError("refusing to overwrite different MAVEN event-search audit")
        AUDIT.write_text(payload, encoding="utf-8", newline="\n")
    else:
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        timestamp = saved.pop("recorded_at", None)
        if (not isinstance(timestamp, str) or
                datetime.fromisoformat(timestamp.replace("Z", "+00:00")).tzinfo is None
                or saved != audit):
            raise ValueError("saved MAVEN event-search audit differs from recomputation")
    print(json.dumps({"status": audit["status"], "records_checked": audit["records_checked"],
                      "arcs": [{"start_utc": arc["start_utc"],
                                "all_arc_events": arc["all_arc_events"],
                                "keyword_arc_hits": len(arc["keyword_arc_hits"]),
                                "keyword_context_hits": len(arc["keyword_context_hits"])}
                               for arc in audit["arcs"]]},
                     indent=2))


if __name__ == "__main__":
    main()
