"""Record the intentionally unavailable T5 source PDF without authorizing use."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/T5_PBS_SOURCE_CONTRACT.json"
METHOD = ROOT / "docs/T5_SOURCE_AVAILABILITY.md"
REQUIREMENTS = ROOT / "requirements-t5-pbs-pdf.txt"
PDF = ROOT / "data/references/t5_pbs/protocols_io_p4rdqv6.pdf"
ACCEPTANCE = ROOT / "artifacts/t5-protocol/acceptance.json"
AUDIT = ROOT / "artifacts/t5-source-availability-audit.json"


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _source(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": _hash(path),
        "bytes": path.stat().st_size,
    }


def _evaluator_input_hash() -> str:
    acceptance = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    value = acceptance.get("evaluator", {}).get("input_hash")
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError("T5 bounded evaluator input hash is unavailable")
    return value


def evaluate() -> dict[str, object]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = contract.get("source", {})
    expected_boundaries = {
        "source_inventory_only": True,
        "local_dynamic_replay_available": False,
        "source_pdf_redistributed": False,
        "execution_allowed": False,
        "independent_procedure_validation": False,
        "biosafety_review_complete": False,
        "human_acceptance": False,
        "claim_status": "unverified",
    }
    expected_doi = "10.17504/protocols.io.p4rdqv6"
    expected_sha256 = "184b4d211aa8c1a2fcde0eb06a2fd8ae57727c28f1a2b41e5fbfd94b5f8c1271"
    expected_bytes = 458059
    if (
        contract.get("schema_version") != "t5-pbs-source-contract-v1"
        or source.get("doi") != expected_doi
        or source.get("pdf_bytes") != expected_bytes
        or source.get("pdf_sha256") != expected_sha256
        or source.get("local_pdf_redistributed") is not False
        or contract.get("boundaries", {}).get("execution_allowed") is not False
    ):
        raise ValueError("T5 source contract is missing its pinned rights and source fields")
    if PDF.is_file():
        raise ValueError(
            "T5 source PDF is present locally; the bounded clean-checkout receipt requires it to be absent"
        )
    if any(path.is_file() is False for path in (CONTRACT, METHOD, REQUIREMENTS, ACCEPTANCE)):
        raise ValueError("T5 source availability inputs are incomplete")
    checks = {
        "source_contract_present": True,
        "doi_pinned": True,
        "expected_pdf_bytes_pinned": True,
        "expected_pdf_sha256_pinned": True,
        "pdf_absent_from_clean_checkout": True,
        "dynamic_pdf_replay_blocked": True,
    }
    return {
        "schema_version": "t5-source-availability-audit-v1",
        "status": "blocked-local-source-not-redistributed",
        "contract_sha256": _hash(CONTRACT),
        "expected_source": {
            "path": PDF.relative_to(ROOT).as_posix(),
            "doi": expected_doi,
            "pdf_bytes": expected_bytes,
            "pdf_sha256": expected_sha256,
        },
        "availability": {
            "local_pdf_exists": False,
            "local_dynamic_replay_available": False,
            "source_pdf_redistributed": False,
        },
        "evaluator_input_hash": _evaluator_input_hash(),
        "checks": checks,
        "boundaries": expected_boundaries,
        "source_files": [_source(path) for path in (
            Path(__file__).resolve(), CONTRACT, METHOD, REQUIREMENTS,
        )],
    }


def _timestamp(value: object) -> None:
    if not isinstance(value, str):
        raise ValueError("T5 source availability receipt has no timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("T5 source availability receipt timestamp is naive")


def verify_saved(audit: dict[str, object] | None = None) -> dict[str, object]:
    saved = audit if audit is not None else json.loads(AUDIT.read_text(encoding="utf-8"))
    expected = evaluate()
    if saved.get("recorded_at") is None:
        raise ValueError("T5 source availability receipt has no timestamp")
    _timestamp(saved["recorded_at"])
    comparable = {key: value for key, value in saved.items() if key != "recorded_at"}
    if comparable != expected:
        raise ValueError("T5 source availability receipt differs from the clean-checkout inputs")
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.write:
        payload = evaluate()
        if AUDIT.exists():
            existing = json.loads(AUDIT.read_text(encoding="utf-8"))
            recorded_at = existing.get("recorded_at")
            _timestamp(recorded_at)
        else:
            recorded_at = datetime.now(timezone.utc).isoformat()
        payload["recorded_at"] = recorded_at
        rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if AUDIT.exists() and AUDIT.read_text(encoding="utf-8") != rendered:
            raise ValueError("refusing to overwrite a different T5 source availability receipt")
        AUDIT.write_text(rendered, encoding="utf-8", newline="\n")
        result = payload
    else:
        result = verify_saved()
    print(json.dumps({
        "status": result["status"],
        "local_pdf_exists": result["availability"]["local_pdf_exists"],
        "dynamic_replay_blocked": result["checks"]["dynamic_pdf_replay_blocked"],
        "claim_status": result["boundaries"]["claim_status"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
