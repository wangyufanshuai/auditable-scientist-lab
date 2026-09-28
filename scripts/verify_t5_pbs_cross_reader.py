"""Cross-check every page of a pinned PBS PDF with independent text extractors."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from pypdf import PdfReader

from verify_t5_pbs_source import AUDIT as SOURCE_AUDIT, CONTRACT as SOURCE_CONTRACT
from verify_t5_pbs_source import PDF, ROOT, evaluate as evaluate_source


CONTRACT = ROOT / "docs/T5_PBS_CROSS_READER_CONTRACT.json"
AUDIT = ROOT / "artifacts/t5-pbs-cross-reader-audit.json"
SOURCE_FILES = (Path(__file__).resolve(), CONTRACT, SOURCE_CONTRACT,
                ROOT / "scripts/verify_t5_pbs_source.py")


def _hash_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _hash(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def _tokens(value: str) -> Counter[str]:
    # ASCII token agreement catches large extraction gaps but does not infer chemistry.
    return Counter(re.findall(r"[a-z0-9]+", value.lower()))


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _fail_closed(pages: list[str], pypdf_pages: list[str], contract: dict[str, Any],
                 source_contract: dict[str, Any]) -> dict[str, Any]:
    if (len(pages) != 3 or len(pypdf_pages) != 3
            or any(not page.strip() for page in [*pages, *pypdf_pages])):
        raise ValueError("T5 cross-reader page inventory differs")
    anchors = []
    for item in source_contract["anchors"]:
        page = pages[item["page"] - 1]
        quote = item["quote"]
        count = page.count(quote)
        if count != (4 if item["key"] == "doi" else 1):
            raise ValueError(f"T5 independent citation missing or multiplied: {item['key']}")
        offset = page.index(quote)
        anchors.append({"key": item["key"], "page": item["page"],
                        "line": _line_number(page, offset), "occurrences": count})
    sections = []
    for item in contract["section_markers"]:
        page = pages[item["page"] - 1]
        if page.count(item["text"]) != 1:
            raise ValueError(f"T5 independent section missing: {item['key']}")
        sections.append({"key": item["key"], "page": item["page"],
                         "line": _line_number(page, page.index(item["text"]))})
    steps = [int(value) for value in re.findall(r"(?m)^([1-6])$", pages[2])]
    if steps != contract["expected_numbered_steps"]:
        raise ValueError("T5 independent numbered-step inventory differs")
    if [page.count("protocols.io |") for page in pages] != [1, 1, 1]:
        raise ValueError("T5 independent page footer inventory differs")
    expected_poppler = contract["poppler_page_text_sha256"]
    expected_pypdf = contract["pypdf_page_text_sha256"]
    page_rows = []
    for index, (poppler_text, pypdf_text) in enumerate(zip(pages, pypdf_pages, strict=True)):
        poppler_hash = _hash_bytes(poppler_text.encode("utf-8"))
        pypdf_hash = _hash_bytes(pypdf_text.encode("utf-8"))
        if poppler_hash != expected_poppler[index] or pypdf_hash != expected_pypdf[index]:
            raise ValueError(f"T5 independent full-page text hash differs: {index + 1}")
        left, right = _tokens(poppler_text), _tokens(pypdf_text)
        common = sum((left & right).values())
        denominator = max(sum(left.values()), sum(right.values()))
        fraction = common / denominator
        if fraction < contract["minimum_shared_ascii_token_fraction_per_page"]:
            raise ValueError(f"T5 cross-reader token coverage fell below gate: {index + 1}")
        lines = poppler_text.splitlines()
        line_hashes = [_hash_bytes(line.encode("utf-8")) for line in lines]
        page_rows.append({
            "page": index + 1, "poppler_text_sha256": poppler_hash,
            "pypdf_text_sha256": pypdf_hash,
            "poppler_ascii_tokens": sum(left.values()),
            "pypdf_ascii_tokens": sum(right.values()),
            "shared_ascii_tokens": common,
            "shared_fraction": round(fraction, 6),
            "poppler_only_tokens": sum((left - right).values()),
            "pypdf_only_tokens": sum((right - left).values()),
            "line_count": len(lines), "line_sha256": line_hashes,
        })
    return {"pages": page_rows, "anchors": anchors, "sections": sections,
            "numbered_steps": steps}


def _negative_controls(pages: list[str], pypdf_pages: list[str],
                       contract: dict[str, Any], source_contract: dict[str, Any]) -> dict[str, bool]:
    mutations = {
        "safety_heading_omission_rejected": (1, "Safety warnings"),
        "numbered_step_omission_rejected": (2, "\n3\n"),
        "non_anchor_text_omission_rejected": (0, "Phosphate-buffered Saline (PBS)"),
    }
    checks = {}
    for key, (index, needle) in mutations.items():
        if pages[index].count(needle) < 1:
            raise ValueError(f"T5 negative-control marker missing: {key}")
        altered = pages.copy()
        altered[index] = altered[index].replace(needle, "", 1)
        try:
            _fail_closed(altered, pypdf_pages, contract, source_contract)
        except ValueError:
            checks[key] = True
        else:
            raise ValueError(f"T5 cross-reader omission control passed unexpectedly: {key}")
    return checks


def evaluate(pdf: Path = PDF, executable: Path | None = None) -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source_contract = json.loads(SOURCE_CONTRACT.read_text(encoding="utf-8"))
    source_saved = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    source_recorded_at = source_saved.pop("recorded_at", None)
    if (contract.get("schema_version") != "t5-pbs-cross-reader-contract-v1"
            or contract.get("source_pdf_sha256") != source_contract["source"]["pdf_sha256"]
            or contract.get("source_contract_sha256") != _hash(SOURCE_CONTRACT)
            or contract.get("pypdf_page_text_sha256") != source_saved["page_text_sha256"]
            or contract.get("boundaries") != {
                "cross_reader_text_coverage": True,
                "source_pdf_redistributed": False,
                "complete_semantic_omission_review": False,
                "independent_procedure_validation": False,
                "biosafety_review_complete": False,
                "human_acceptance": False,
                "execution_allowed": False,
                "claim_status": "unverified",
            }
            or not source_recorded_at or source_saved != evaluate_source(pdf)):
        raise ValueError("T5 cross-reader source, rights, or boundary differs")
    if _hash(pdf) != contract["source_pdf_sha256"]:
        raise ValueError("T5 cross-reader PDF hash differs")
    executable = executable or Path(shutil.which("pdftotext") or "")
    if not executable.is_file():
        raise FileNotFoundError("pdftotext executable is unavailable")
    tool = contract["poppler"]
    version_result = subprocess.run([str(executable), "-v"], capture_output=True,
                                    text=True, check=False, timeout=10)
    version_text = version_result.stdout + version_result.stderr
    if (f"pdftotext version {tool['version']}" not in version_text
            or _hash(executable) != tool["local_executable_sha256"]
            or executable.stat().st_size != tool["local_executable_bytes"]
            or tool["binary_redistributed"] is not False
            or tool["binary_distribution_license_reviewed"] is not False):
        raise ValueError("T5 independent extractor identity or rights boundary differs")
    output = subprocess.run(
        [str(executable), *tool["arguments"], str(pdf), "-"],
        capture_output=True, check=True, timeout=20,
    ).stdout.decode("utf-8", errors="strict")
    pages = [page for page in output.split("\f") if page.strip()]
    pypdf_pages = [page.extract_text() for page in PdfReader(str(pdf)).pages]
    inventory = _fail_closed(pages, pypdf_pages, contract, source_contract)
    controls = _negative_controls(pages, pypdf_pages, contract, source_contract)
    return {
        "schema_version": "t5-pbs-cross-reader-audit-v1",
        "status": "verified-three-page-cross-reader-text-coverage-only",
        "source_pdf_sha256": contract["source_pdf_sha256"],
        "source_contract_sha256": contract["source_contract_sha256"],
        "cross_reader_contract_sha256": _hash(CONTRACT),
        "extractors": {
            "pypdf_version": version("pypdf"),
            "pdftotext_version": tool["version"],
            "pdftotext_executable_sha256": tool["local_executable_sha256"],
            "pdftotext_binary_redistributed": False,
            "pdftotext_binary_distribution_license_reviewed": False,
        },
        **inventory, "negative_controls": controls,
        "boundaries": contract["boundaries"],
        "source_files": [{"path": path.relative_to(ROOT).as_posix(),
                          "sha256": _hash(path), "bytes": path.stat().st_size}
                         for path in SOURCE_FILES],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    current = evaluate()
    if args.write:
        if AUDIT.exists():
            raise FileExistsError(f"refusing to overwrite T5 cross-reader audit: {AUDIT}")
        current["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    else:
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        stamp = saved.pop("recorded_at", None)
        if (not isinstance(stamp, str)
                or datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None
                or saved != current):
            raise ValueError("T5 cross-reader audit differs from pinned local extractors")
    print(json.dumps({"status": current["status"],
                      "pages": len(current["pages"]),
                      "anchors": len(current["anchors"]),
                      "numbered_steps": len(current["numbered_steps"]),
                      "negative_controls": current["negative_controls"],
                      "execution_allowed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
