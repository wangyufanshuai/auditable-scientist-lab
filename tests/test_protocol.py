"""T5 evidence integrity and execution-boundary regressions."""

from __future__ import annotations

from hashlib import sha256
import pytest
from pydantic import ValidationError

from auditable_scientist.tracks.protocol import ProtocolSpec, extract_teaching_protocol, verify_protocol


TEXT = (
    "step-1 action=mix reagent=buffer volume=10 uL temperature=22 C duration=5 min\n"
    "step-2 action=mix reagent=water volume=5 uL temperature=24 C duration=10 min\n"
)


def fixture() -> ProtocolSpec:
    return extract_teaching_protocol(
        TEXT, protocol_id="teaching-1", document_id="synthetic-1",
        min_temperature_c=20, max_temperature_c=30, max_total_volume_ul=20,
    )


def test_all_fields_have_exact_resolved_spans_and_no_execution_authority() -> None:
    protocol = fixture()
    result = verify_protocol(protocol)
    assert result.passed and result.checked_citations == 10
    assert result.review_status == "text-reviewed"
    assert result.evidence_level == "demo"
    assert result.requires_human_review and not result.execution_allowed
    for step in protocol.steps:
        for citation in step.citations:
            assert protocol.documents[0].text[citation.start:citation.end] == citation.excerpt


def test_hash_span_value_and_missing_citation_are_independent_gates() -> None:
    protocol = fixture()
    document = protocol.documents[0]
    altered_document = document.model_copy(update={"text": document.text.replace("buffer", "water", 1)})
    changed = verify_protocol(protocol.model_copy(update={"documents": [altered_document]}))
    assert "document-hash:synthetic-1" in changed.failures
    assert "citation-span:step-1:reagent" in changed.failures

    step = protocol.steps[0]
    bad_volume = step.model_copy(update={"volume_ul": 11.0})
    assert "citation-value:step-1:volume_ul" in verify_protocol(protocol.model_copy(update={"steps": [bad_volume, protocol.steps[1]]})).failures

    misplaced = step.citations[0].model_copy(update={"start": step.citations[0].start + 1})
    altered_step = step.model_copy(update={"citations": [misplaced, *step.citations[1:]]})
    assert "citation-span:step-1:action" in verify_protocol(protocol.model_copy(update={"steps": [altered_step, protocol.steps[1]]})).failures

    incomplete = step.model_copy(update={"citations": step.citations[:-1]})
    assert "missing-citation:step-1:duration_min" in verify_protocol(protocol.model_copy(update={"steps": [incomplete, protocol.steps[1]]})).failures


def test_unsupported_material_or_action_requires_review_and_bad_source_blocks() -> None:
    protocol = extract_teaching_protocol(
        TEXT.replace("action=mix", "action=unknown", 1),
        protocol_id="unsafe-1", document_id="synthetic-2",
        min_temperature_c=20, max_temperature_c=30, max_total_volume_ul=20,
    )
    result = verify_protocol(protocol)
    assert not result.passed and not result.execution_allowed
    assert "requires-expert-review:step-1" in result.failures
    blocked = fixture()
    blocked_document = blocked.documents[0].model_copy(update={"provenance_status": "blocked"})
    assert "document-provenance:synthetic-1" in verify_protocol(blocked.model_copy(update={"documents": [blocked_document]})).failures


def test_reused_values_cannot_be_cited_from_another_step_or_hide_extra_text() -> None:
    protocol = fixture()
    first, second = protocol.steps
    swapped_first = first.model_copy(update={"citations": [second.citations[0], *first.citations[1:]]})
    swapped_second = second.model_copy(update={"citations": [first.citations[0], *second.citations[1:]]})
    swapped = verify_protocol(protocol.model_copy(update={"steps": [swapped_first, swapped_second]}))
    assert "citation-step:step-1:action" in swapped.failures
    assert "citation-step:step-2:action" in swapped.failures

    document = protocol.documents[0]
    extra_text = document.text + "unparsed instruction\n"
    changed_document = document.model_copy(update={
        "text": extra_text,
        "text_sha256": sha256(extra_text.encode("utf-8")).hexdigest(),
    })
    changed = verify_protocol(protocol.model_copy(update={"documents": [changed_document]}))
    assert any(item.startswith("document-grammar:") for item in changed.failures)

    reversed_text = "".join(reversed(TEXT.splitlines(keepends=True)))
    reversed_document = document.model_copy(update={
        "text": reversed_text,
        "text_sha256": sha256(reversed_text.encode("utf-8")).hexdigest(),
    })
    assert "document-step-order" in verify_protocol(protocol.model_copy(update={"documents": [reversed_document]})).failures


def test_unparsed_text_and_nonfinite_measurements_fail_closed() -> None:
    with pytest.raises(ValueError, match="unparsed teaching line"):
        extract_teaching_protocol(
            TEXT + "unsupported line\n", protocol_id="p", document_id="d",
            min_temperature_c=20, max_temperature_c=30, max_total_volume_ul=20,
        )
    payload = fixture().model_dump(mode="json")
    payload["steps"][0]["volume_ul"] = float("inf")
    with pytest.raises(ValidationError):
        ProtocolSpec.model_validate(payload)
