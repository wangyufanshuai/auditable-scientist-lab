"""Verify a bounded, agent-authored visual review of the pinned PBS PDF."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/T5_PBS_VISUAL_REVIEW_CONTRACT.json"
SOURCE = ROOT / "docs/T5_PBS_SOURCE_CONTRACT.json"
CROSS_READER = ROOT / "docs/T5_PBS_CROSS_READER_CONTRACT.json"
AUDIT = ROOT / "artifacts/t5-pbs-visual-review-audit.json"
ACCEPTANCE = ROOT / "artifacts/t5-protocol/acceptance.json"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _source(path: Path) -> dict[str, object]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "sha256": _sha(path), "bytes": path.stat().st_size}


def evaluate() -> dict[str, object]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    cross_reader = json.loads(CROSS_READER.read_text(encoding="utf-8"))
    pdf_hash = "184b4d211aa8c1a2fcde0eb06a2fd8ae57727c28f1a2b41e5fbfd94b5f8c1271"
    expected_flags = [
        "page-2-possible-ui-residue-in-safety-box",
        "page-3-chemical-glyph-and-separator-ambiguity",
        "material-cards-not-yet-structured",
        "manual-visual-review-not-human-acceptance",
    ]
    expected_boundaries = {
        "agent_authored_visual_observations": True,
        "complete_visual_omission_review": False,
        "machine_readable_recipe": False,
        "independent_procedure_validation": False,
        "biosafety_review_complete": False,
        "human_acceptance": False,
        "execution_allowed": False,
        "claim_status": "unverified",
    }
    pages = contract.get("pages", [])
    renderer = contract.get("renderer", {})
    if (contract.get("schema_version") != "t5-pbs-visual-review-contract-v1"
            or contract.get("scope") != "agent-authored-read-only-page-review-not-human-acceptance"
            or contract.get("source_pdf_sha256") != pdf_hash
            or contract.get("source_pdf_bytes") != 458059
            or source.get("source", {}).get("pdf_sha256") != pdf_hash
            or source["source"].get("pdf_bytes") != contract["source_pdf_bytes"]
            or cross_reader.get("source_pdf_sha256") != pdf_hash
            or cross_reader.get("source_contract_sha256") != _sha(SOURCE)
            or contract.get("review_flags") != expected_flags
            or contract.get("boundaries") != expected_boundaries
            or renderer.get("name") != "pdftoppm"
            or renderer.get("arguments") != ["-f", "1", "-l", "3", "-r", "125", "-png"]
            or renderer.get("rendered_images_redistributed") is not False
            or not re.fullmatch(r"[a-f0-9]{64}", renderer.get("local_executable_sha256", ""))
            or len(pages) != 3
            or [row.get("page") for row in pages] != [1, 2, 3]
            or any(not re.fullmatch(r"[a-f0-9]{64}", row.get("render_sha256", ""))
                   or not row.get("observations") for row in pages)):
        raise ValueError("T5 visual review source, page record, or evidence boundary differs")
    return {
        "schema_version": "t5-pbs-visual-review-audit-v1",
        "status": "recorded-agent-visual-observations-only",
        "source_pdf_sha256": pdf_hash,
        "evaluator_input_hash": json.loads(ACCEPTANCE.read_text(encoding="utf-8"))["evaluator"]["input_hash"],
        "visual_contract_sha256": _sha(CONTRACT),
        "source_contract_sha256": _sha(SOURCE),
        "cross_reader_contract_sha256": _sha(CROSS_READER),
        "page_render_sha256": [row["render_sha256"] for row in pages],
        "review_flags": expected_flags,
        "boundaries": expected_boundaries,
        "source_files": [_source(path) for path in (Path(__file__).resolve(), CONTRACT, SOURCE, CROSS_READER)],
    }


def verify_source(pdf: Path) -> None:
    """Rerender the local source when supplied; never copy it into the repo."""
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if pdf.stat().st_size != contract["source_pdf_bytes"] or _sha(pdf) != contract["source_pdf_sha256"]:
        raise ValueError("T5 visual review source PDF differs")
    executable = Path(shutil.which("pdftoppm") or "")
    renderer = contract["renderer"]
    if not executable.is_file() or _sha(executable) != renderer["local_executable_sha256"]:
        raise ValueError("T5 visual review renderer identity differs")
    result = subprocess.run([str(executable), "-v"], capture_output=True, text=True,
                            check=False, timeout=10)
    if f"pdftoppm version {renderer['version']}" not in result.stdout + result.stderr:
        raise ValueError("T5 visual review renderer version differs")
    with tempfile.TemporaryDirectory(prefix="t5-pbs-render-") as temporary:
        prefix = Path(temporary) / "pbs-page"
        subprocess.run([str(executable), *renderer["arguments"], str(pdf), str(prefix)],
                       capture_output=True, check=True, timeout=30)
        for row in contract["pages"]:
            if _sha(prefix.parent / f"pbs-page-{row['page']}.png") != row["render_sha256"]:
                raise ValueError(f"T5 visual review page render differs: {row['page']}")


def verify_saved(audit: dict[str, object] | None = None) -> dict[str, object]:
    saved = audit if audit is not None else json.loads(AUDIT.read_text(encoding="utf-8"))
    stamp = saved.get("recorded_at")
    if not isinstance(stamp, str):
        raise ValueError("T5 visual review timestamp missing")
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("T5 visual review timestamp is naive")
    if {key: value for key, value in saved.items() if key != "recorded_at"} != evaluate():
        raise ValueError("T5 visual review receipt differs")
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--source-pdf", type=Path,
                        help="optional local PDF for exact rerender; never redistributed")
    args = parser.parse_args()
    if args.source_pdf is not None:
        verify_source(args.source_pdf)
    if args.write:
        if AUDIT.exists():
            raise FileExistsError(f"refusing to overwrite T5 visual review audit: {AUDIT}")
        result = evaluate()
        result["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    else:
        result = verify_saved()
    print(json.dumps({"status": result["status"], "pages": len(result["page_render_sha256"]),
                      "claim_status": result["boundaries"]["claim_status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
