"""Offline registration contracts; registration does not dispatch scientific tools."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from importlib.resources import files
import json
from pathlib import Path, PurePosixPath
import re

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError


REGISTRY_ROW = "bounded-track-registry"
BOUNDARIES = {
    "claim_status": "unverified", "execution_allowed": False, "real_data": False,
    "research_candidate": False, "public_release_allowed": False,
    "scientific_validity": False, "publication_ready": False,
}


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(text: str) -> dict:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant: {value}")

    result = json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ValueError("expected a JSON object")
    return result


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def bundled_registry() -> dict:
    """Load declarations only. Wheel resources do not include acceptance evidence."""
    return load_json(files("auditable_scientist").joinpath(
        "_resources/examples/track-registry/registry.json").read_text(encoding="utf-8"))


def bundled_schema() -> dict:
    return load_json(files("auditable_scientist").joinpath(
        "_resources/schemas/track-registry-v1.json").read_text(encoding="utf-8"))


def validate_contract(registry: dict, schema: dict | None = None) -> list[str]:
    """Validate an extensible declaration; no acceptance or science is inferred."""
    schema = schema if schema is not None else bundled_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(registry)
    tracks = registry["tracks"]
    ids = [item["track_id"] for item in tracks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate registry track ID")
    for track in tracks:
        receipts = track["required_receipts"]
        if track["acceptance"] not in receipts:
            raise ValueError("acceptance must be a required receipt")
        for refs in track["review_evidence"].values():
            if not set(refs) <= set(receipts):
                raise ValueError("review evidence must bind required receipts")
        if track["source_rights_status"] == "partially-reviewed" and not track["review_evidence"]["source_rights"]:
            raise ValueError("partial rights review needs evidence references")
        if track["human_review_status"] != "not-completed" and not track["review_evidence"]["human_review"]:
            raise ValueError("review annotation needs evidence references")
    return ids


def safe_file(root: Path, relative: str) -> Path:
    """Reject traversal, Windows aliases, and links before reading repository data."""
    parts = PurePosixPath(relative).parts
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    if (not parts or PurePosixPath(relative).as_posix() != relative
            or any(not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", part)
                   or part.endswith(".") or part.split(".")[0].upper() in reserved for part in parts)):
        raise ValueError(f"unsafe evidence path: {relative}")
    root = root.resolve()
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError(f"linked evidence path: {relative}")
    if not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError(f"missing or unsafe evidence path: {relative}")
    if path.stat().st_nlink > 1:
        raise ValueError(f"hard-linked evidence path: {relative}")
    return path


def acceptance_projection(package: dict) -> dict:
    """Exclude only the self-referencing registry row; preserve every other field."""
    result = deepcopy(package)
    checks = result.get("checks")
    if not isinstance(checks, list) or not checks or any(not isinstance(row, dict) for row in checks):
        raise ValueError("acceptance checks are missing")
    names = [row.get("name") for row in checks]
    if any(not isinstance(name, str) or not name for name in names) or len(names) != len(set(names)):
        raise ValueError("duplicate or invalid acceptance check name")
    result["checks"] = [row for row in checks if row["name"] != REGISTRY_ROW]
    if not result["checks"]:
        raise ValueError("acceptance lacks independent checks")
    if any(row.get("exit_code") != 0 or type(row.get("exit_code")) is not int
           for row in result["checks"]):
        raise ValueError("acceptance contains unsuccessful checks")
    return result


def _index(value: dict, label: str) -> dict:
    tracks = value.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise ValueError(f"{label} tracks are missing")
    ids = [item.get("track_id") for item in tracks]
    if any(not isinstance(key, str) for key in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"duplicate or invalid {label} track ID")
    return dict(zip(ids, tracks))


def validate_evidence(registry: dict, root: Path, *, schema: dict | None = None,
                      overrides: dict[str, bytes] | None = None) -> dict:
    """Reconcile declarations with a supplied portfolio and fingerprint evidence.

    Overrides are complete proposed acceptance/status bytes used by regeneration.
    Files must still exist and pass the same path checks; overrides cannot add files.
    """
    ids = validate_contract(registry, schema)
    overrides = overrides or {}

    def read(relative: str) -> bytes:
        path = safe_file(root, relative)
        return overrides[relative] if relative in overrides else path.read_bytes()

    status = load_json(read("artifacts/portfolio-status.json").decode("utf-8"))
    portfolio = load_json(read("artifacts/track-portfolio.json").decode("utf-8"))
    if (status.get("schema_version") != "portfolio-status-v1"
            or status.get("public_release_allowed") is not False
            or portfolio.get("schema_version") != "track-portfolio-v1"
            or portfolio.get("status") != "bounded-slices-accepted"
            or portfolio.get("global_boundaries") != [
                "No real-data claim", "No autonomous wet-lab execution", "No publication or novelty claim"]):
        raise ValueError("portfolio is not a bounded contract")
    statuses = _index(status, "status")
    evaluators = _index(portfolio, "portfolio")
    if set(ids) != set(statuses) or set(ids) != set(evaluators):
        raise ValueError("registry membership differs from supplied portfolios")
    receipts = {}
    for track in registry["tracks"]:
        track_id = track["track_id"]
        entry, evaluator = statuses[track_id], evaluators[track_id]
        if any(track[key] != entry.get(key) for key in ("acceptance", "state", "next_step", "open_gates")):
            raise ValueError(f"{track_id} differs from portfolio status")
        if (entry.get("public_release") is not False or evaluator.get("passed") is not True
                or evaluator.get("negative_case_passed") is not True
                or track["evidence_level"] != evaluator.get("evidence_level")
                or track["evaluator_id"] != evaluator.get("evaluator_id")):
            raise ValueError(f"{track_id} evaluator identity or boundary differs")
        package = load_json(read(track["acceptance"]).decode("utf-8"))
        projection = acceptance_projection(package)
        if package.get("status") != "accepted-with-bounded-scope":
            raise ValueError(f"{track_id} acceptance exceeds bounded scope")
        if track["acceptance_contract"] == "root-v1":
            boundaries = package.get("scientific_boundaries", {})
            if (package.get("schema_version") != "acceptance-v1"
                    or package.get("scope", {}).get("track") != track_id
                    or evaluator.get("result", {}).get("acceptance") != track["acceptance"]
                    or any(boundaries.get(key) is not False for key in (
                        "novel_physics", "production_readiness", "publication_readiness"))):
                raise ValueError(f"{track_id} root acceptance boundary or identity differs")
        else:
            boundaries = package.get("evidence_boundaries", {})
            if (package.get("track") != track_id or package.get("execution") != "offline"
                    or package.get("evaluator") != evaluator):
                raise ValueError(f"{track_id} acceptance evaluator or execution differs")
        expected = {"demo": True, "real_data": False, "research_candidate": False,
                    "validated_reproduction": track["evidence_level"] == "validated-reproduction"}
        if any(boundaries.get(key) is not value for key, value in expected.items()):
            raise ValueError(f"{track_id} acceptance boundary was widened")
        for relative in track["required_receipts"]:
            content = read(relative)
            binding = "file-bytes"
            if track["acceptance_contract"] == "root-v1" and relative == track["acceptance"]:
                content = canonical_bytes(projection)
                binding = "canonical-acceptance-excluding-registry-row"
            fingerprint = {"path": relative, "sha256": hashlib.sha256(content).hexdigest(),
                           "bytes": len(content), "binding": binding}
            if relative in receipts and receipts[relative] != fingerprint:
                raise ValueError("conflicting evidence bindings")
            receipts[relative] = fingerprint
    return {
        "track_ids": ids, "track_count": len(ids), "required_receipt_count": len(receipts),
        "required_receipts": [receipts[key] for key in sorted(receipts)],
        "boundaries": deepcopy(BOUNDARIES),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, help="default: bundled declarations")
    parser.add_argument("--root", type=Path, help="explicit evidence checkout, never inferred from wheel")
    args = parser.parse_args()
    try:
        registry = load_json(args.registry.read_text(encoding="utf-8")) if args.registry else bundled_registry()
        ids = validate_contract(registry)
        if args.root:
            result = {"status": "verified-bounded-registry-evidence", **validate_evidence(registry, args.root)}
        else:
            result = {"status": "valid-declaration-only", "track_ids": ids,
                      "track_count": len(ids), "evidence_checked": False, "boundaries": deepcopy(BOUNDARIES)}
    except (ValueError, OSError, SchemaError, ValidationError) as error:
        parser.exit(1, f"registry validation failed: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
