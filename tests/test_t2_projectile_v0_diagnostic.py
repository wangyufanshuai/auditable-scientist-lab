"""The T2 v0 diagnostic stays post-hoc and rejects provenance overclaims."""

from copy import deepcopy
import json

import pytest

from scripts import verify_t2_projectile_v0_diagnostic as diagnostic


def test_saved_diagnostic_is_bounded() -> None:
    result = diagnostic.verify_saved()
    assert result["status"] == "verified-posthoc-v0-provenance-diagnostic-only"
    assert result["trial_count"] == 30
    assert result["sample_count"] == 179
    assert len(result["declared_speed_above_paper_bound_trials"]) == 15
    assert result["comparison"]["within_0_1_m_s"] == 28
    assert result["boundaries"]["v0_role_resolved"] is False
    assert result["boundaries"]["model_fit_admitted"] is False


@pytest.mark.parametrize("mutation", ["promotion", "difference", "trial"])
def test_saved_diagnostic_rejects_tampering(mutation: str) -> None:
    saved = json.loads(diagnostic.AUDIT.read_text(encoding="utf-8"))
    changed = deepcopy(saved)
    if mutation == "promotion":
        changed["boundaries"]["v0_role_resolved"] = True
    elif mutation == "difference":
        changed["comparison"]["within_0_1_m_s"] = 30
    else:
        changed["trial_comparisons"].pop()
    with pytest.raises(ValueError, match="receipt differs"):
        diagnostic.verify_saved(changed)
