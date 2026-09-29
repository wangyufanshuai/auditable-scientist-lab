"""The PBS visual review remains hash-bound and cannot promote the protocol."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import verify_t5_pbs_visual_review


def test_saved_visual_review_is_bounded() -> None:
    result = verify_t5_pbs_visual_review.verify_saved()
    assert result["status"] == "recorded-agent-visual-observations-only"
    assert result["boundaries"]["machine_readable_recipe"] is False
    assert result["boundaries"]["human_acceptance"] is False
    assert "page-2-possible-ui-residue-in-safety-box" in result["review_flags"]


@pytest.mark.parametrize("mutation", ["hash", "promotion", "flag"])
def test_saved_visual_review_rejects_tampering(mutation: str) -> None:
    saved = json.loads(verify_t5_pbs_visual_review.AUDIT.read_text(encoding="utf-8"))
    changed = deepcopy(saved)
    if mutation == "hash":
        changed["page_render_sha256"][1] = "0" * 64
    elif mutation == "promotion":
        changed["boundaries"]["human_acceptance"] = True
    else:
        changed["review_flags"].pop()
    with pytest.raises(ValueError, match="receipt differs"):
        verify_t5_pbs_visual_review.verify_saved(changed)


def test_render_check_rejects_wrong_source_before_using_renderer(tmp_path: Path) -> None:
    wrong_source = tmp_path / "source.pdf"
    wrong_source.write_bytes(b"not the cited PDF")
    with pytest.raises(ValueError, match="source PDF differs"):
        verify_t5_pbs_visual_review.verify_source(wrong_source)
