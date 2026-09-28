"""Audit a licensed real protocol PDF as cited text, without authorizing execution."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import metadata, version
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/T5_PBS_SOURCE_CONTRACT.json"
PDF = ROOT / "data/references/t5_pbs/protocols_io_p4rdqv6.pdf"
AUDIT = ROOT / "artifacts/t5-pbs-source-audit.json"
SOURCE_FILES = (Path(__file__).resolve(), CONTRACT,
                ROOT / "requirements-t5-pbs-pdf.txt")


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _source(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(),
            "sha256": _hash(path), "bytes": path.stat().st_size}


def evaluate(pdf: Path = PDF) -> dict:
    from pypdf import PdfReader

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = contract["source"]
    expected_boundaries = {
        "real_source_document": True, "rights_declaration_present": True,
        "independent_procedure_validation": False, "complete_safety_review": False,
        "machine_executable_protocol": False, "human_acceptance": False,
        "execution_allowed": False, "claim_status": "unverified",
    }
    if (contract.get("schema_version") != "t5-pbs-source-contract-v1"
            or contract.get("status") != "posthoc-source-intake-not-scientific-validation"
            or contract.get("boundaries") != expected_boundaries
            or contract["source"].get("doi") != "10.17504/protocols.io.p4rdqv6"
            or contract["source"].get("local_pdf_redistributed") is not False
            or contract["source"].get("attribution_required") is not True):
        raise ValueError("T5 source scope or rights contract differs")
    if (pdf.stat().st_size != source["pdf_bytes"] or _hash(pdf) != source["pdf_sha256"]):
        raise ValueError("T5 source PDF differs from pinned bytes")
    reader = contract["reader"]
    if (version(reader["package"]) != reader["version"]
            or metadata(reader["package"]).get("License-Expression") !=
            reader["license_expression"]):
        raise ValueError("T5 PDF reader version or license differs")
    pages = [page.extract_text() for page in PdfReader(str(pdf)).pages]
    if len(pages) != source["pdf_pages"] or any(not text for text in pages):
        raise ValueError("T5 source page inventory differs")
    anchor_rows = []
    for anchor in contract["anchors"]:
        page_number, quote = anchor["page"], anchor["quote"]
        if not isinstance(page_number, int) or not 1 <= page_number <= len(pages):
            raise ValueError("T5 anchor page differs")
        page = pages[page_number-1]
        count = page.count(quote)
        if not count:
            raise ValueError(f"T5 anchor missing: {anchor['key']}")
        start = page.index(quote)
        anchor_rows.append({"key": anchor["key"], "page": page_number,
                            "start": start, "end": start+len(quote),
                            "excerpt": quote, "occurrences_on_page": count,
                            "page_text_sha256": sha256(page.encode("utf-8")).hexdigest()})
    if (len({row["key"] for row in anchor_rows}) != len(anchor_rows)
            or [row["key"] for row in anchor_rows] != [
                "doi", "license", "license_attribution", "self_reported_working",
                "sds_warning", "concentration_branch", "concentration_alternative",
                "ph_alternative", "acid", "optional_depc", "autoclave"]):
        raise ValueError("T5 source anchor inventory differs")
    page3 = pages[2]
    markers = list(re.finditer(r"(?m)^([1-6])\s+", page3))
    if [int(match.group(1)) for match in markers] != list(range(1, 7)):
        raise ValueError("T5 source PDF does not yield six ordered steps")
    footer = page3.find("protocols.io |", markers[-1].end())
    if footer <= markers[-1].end():
        raise ValueError("T5 source footer or last step differs")
    steps = []
    for index, marker in enumerate(markers):
        end = markers[index+1].start() if index+1 < len(markers) else footer
        text = page3[marker.start():end].strip()
        steps.append({"step_number": index+1, "page": 3,
                      "start": marker.start(), "end": marker.start()+len(text),
                      "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
                      "excerpt_prefix": text[:48]})
    page_hashes = [sha256(page.encode("utf-8")).hexdigest() for page in pages]
    return {
        "schema_version": "t5-pbs-source-audit-v1",
        "status": "verified-source-document-and-review-flags-only",
        "contract_sha256": _hash(CONTRACT),
        "source_pdf_sha256": source["pdf_sha256"],
        "source": {key: source[key] for key in (
            "title", "author", "publisher", "doi", "pdf_url", "published_date",
            "last_modified_date_in_pdf", "protocol_integer_id", "pdf_bytes",
            "pdf_pages", "license_declaration", "license_location",
            "attribution_required", "local_pdf_redistributed")},
        "reader": reader,
        "page_text_sha256": page_hashes,
        "anchors": anchor_rows,
        "step_inventory": steps,
        "review_flags": contract["review_flags"],
        "boundaries": expected_boundaries,
        "source_files": [_source(path) for path in SOURCE_FILES],
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
            raise ValueError("refusing to overwrite different T5 source audit")
        AUDIT.write_text(payload, encoding="utf-8", newline="\n")
    else:
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        stamp = saved.pop("recorded_at", None)
        if (not isinstance(stamp, str)
                or datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None
                or saved != audit):
            raise ValueError("T5 source audit differs from pinned local PDF")
    print(json.dumps({"status": audit["status"], "pages": len(audit["page_text_sha256"]),
                      "steps": len(audit["step_inventory"]),
                      "review_flags": len(audit["review_flags"]),
                      "execution_allowed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
