"""Independent PDF extraction and omission checks for the T5 source."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_optional_acceptance import _t5_cross_reader_receipt  # noqa: E402
from verify_t5_pbs_cross_reader import (  # noqa: E402
    AUDIT, CONTRACT, PDF, SOURCE_CONTRACT, _fail_closed, evaluate,
)


def _texts() -> tuple[list[str], list[str]]:
    from pypdf import PdfReader

    executable = shutil.which("pdftotext")
    if not PDF.is_file() or not executable:
        pytest.skip("pinned PDF or Poppler executable is unavailable")
    output = subprocess.run(
        [executable, "-enc", "UTF-8", "-eol", "unix", str(PDF), "-"],
        capture_output=True, check=True, timeout=20,
    ).stdout.decode("utf-8")
    return ([page for page in output.split("\f") if page.strip()],
            [page.extract_text() for page in PdfReader(str(PDF)).pages])


def test_cross_reader_audit_covers_three_pages_and_stays_read_only() -> None:
    saved = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert _t5_cross_reader_receipt(verify_dynamic=False)["status"] == saved["status"]
    executable = shutil.which("pdftotext")
    if not PDF.is_file() or not executable:
        pytest.skip("pinned PDF or Poppler executable is unavailable")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if sha256(Path(executable).read_bytes()).hexdigest() != contract["poppler"]["local_executable_sha256"]:
        pytest.skip("different Poppler binary; static receipt remains checkable")
    current = evaluate()
    saved.pop("recorded_at")
    assert current == saved
    assert [row["page"] for row in current["pages"]] == [1, 2, 3]
    assert len(current["anchors"]) == 11
    assert current["numbered_steps"] == [1, 2, 3, 4, 5, 6]
    assert all(row["shared_fraction"] >= 0.94 for row in current["pages"])
    assert current["boundaries"]["execution_allowed"] is False
    assert current["boundaries"]["claim_status"] == "unverified"


@pytest.mark.parametrize("page,needle,reason", [
    (1, "Safety warnings", "section"),
    (2, "\n3\n", "numbered-step"),
    (0, "Phosphate-buffered Saline (PBS)", "full-page text hash"),
])
def test_cross_reader_rejects_text_omission(
    page: int, needle: str, reason: str,
) -> None:
    poppler_pages, pypdf_pages = _texts()
    assert needle in poppler_pages[page]
    poppler_pages[page] = poppler_pages[page].replace(needle, "", 1)
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = json.loads(SOURCE_CONTRACT.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match=reason):
        _fail_closed(poppler_pages, pypdf_pages, contract, source)


@pytest.mark.parametrize("mutation", [
    "missing_page", "claimed_execution", "missing_negative_control", "changed_source_hash",
])
def test_cross_reader_projection_rejects_mutated_receipt(mutation: str) -> None:
    audit = deepcopy(json.loads(AUDIT.read_text(encoding="utf-8")))
    if mutation == "missing_page":
        audit["pages"].pop()
    elif mutation == "claimed_execution":
        audit["boundaries"]["execution_allowed"] = True
    elif mutation == "missing_negative_control":
        audit["negative_controls"]["safety_heading_omission_rejected"] = False
    else:
        audit["source_files"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        _t5_cross_reader_receipt(audit, verify_dynamic=False)
