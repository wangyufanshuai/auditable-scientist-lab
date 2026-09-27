"""T5: offline textual protocol review with field-level evidence, never execution."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from hashlib import sha256
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FIELDS = ("action", "reagent", "volume_ul", "temperature_c", "duration_min")
SAFE_ACTIONS = frozenset({"mix", "wait"})
SAFE_REAGENTS = frozenset({"buffer", "water"})
NUMBER_WITH_UNIT = {
    "volume_ul": re.compile(r"^([0-9]+(?:\.[0-9]+)?) uL$"),
    "temperature_c": re.compile(r"^(-?[0-9]+(?:\.[0-9]+)?) C$"),
    "duration_min": re.compile(r"^([0-9]+(?:\.[0-9]+)?) min$"),
}
TEACHING_LINE = re.compile(
    r"(?P<step_id>step-[0-9]+) action=(?P<action>[A-Za-z_-]+) "
    r"reagent=(?P<reagent>[A-Za-z_-]+) "
    r"volume=(?P<volume_ul>[0-9]+(?:\.[0-9]+)? uL) "
    r"temperature=(?P<temperature_c>-?[0-9]+(?:\.[0-9]+)? C) "
    r"duration=(?P<duration_min>[0-9]+(?:\.[0-9]+)? min)"
)


class ProtocolDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_type: Literal["synthetic-teaching-fixture"]
    provenance_status: Literal["unverified", "blocked"]


class ProtocolCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    field: Literal["action", "reagent", "volume_ul", "temperature_c", "duration_min"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    excerpt: str = Field(min_length=1)
    extraction_method: Literal["exact", "inferred"]


class ProtocolStep(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    step_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    reagent: str = Field(min_length=1)
    volume_ul: float = Field(gt=0)
    temperature_c: float
    duration_min: float = Field(gt=0)
    citations: list[ProtocolCitation] = Field(min_length=1)


class ProtocolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    protocol_id: str = Field(min_length=1)
    documents: list[ProtocolDocument] = Field(min_length=1)
    steps: list[ProtocolStep] = Field(min_length=1)
    min_temperature_c: float
    max_temperature_c: float
    max_total_volume_ul: float = Field(gt=0)


class ProtocolVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator_id: str = "bio-chem-text-protocol-v2"
    passed: bool
    failures: list[str]
    checked_citations: int = Field(ge=0)
    review_status: Literal["text-reviewed", "blocked"]
    requires_human_review: bool = True
    execution_allowed: bool = False
    evidence_level: Literal["demo"] = "demo"
    notes: list[str]


def extract_teaching_protocol(
    text: str, *, protocol_id: str, document_id: str,
    min_temperature_c: float, max_temperature_c: float, max_total_volume_ul: float,
) -> ProtocolSpec:
    """Locate every field in a deliberately small, synthetic line grammar."""
    if not text or "\r" in text:
        raise ValueError("teaching text must be nonempty LF text")
    document = ProtocolDocument(
        document_id=document_id, text=text,
        text_sha256=sha256(text.encode("utf-8")).hexdigest(),
        source_type="synthetic-teaching-fixture", provenance_status="unverified",
    )
    steps: list[ProtocolStep] = []
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.removesuffix("\n")
        match = TEACHING_LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"unparsed teaching line at character {offset}")
        citations = [
            ProtocolCitation(
                document_id=document_id, field=field, start=offset + match.start(field),
                end=offset + match.end(field), excerpt=match.group(field), extraction_method="exact",
            )
            for field in FIELDS
        ]
        steps.append(ProtocolStep(
            step_id=match.group("step_id"), action=match.group("action"),
            reagent=match.group("reagent"),
            volume_ul=float(match.group("volume_ul").split()[0]),
            temperature_c=float(match.group("temperature_c").split()[0]),
            duration_min=float(match.group("duration_min").split()[0]),
            citations=citations,
        ))
        offset += len(raw_line)
    return ProtocolSpec(
        protocol_id=protocol_id, documents=[document], steps=steps,
        min_temperature_c=min_temperature_c,
        max_temperature_c=max_temperature_c,
        max_total_volume_ul=max_total_volume_ul,
    )


def _value_matches(step: ProtocolStep, citation: ProtocolCitation) -> bool:
    value = getattr(step, citation.field)
    if citation.field in ("action", "reagent"):
        return citation.excerpt == value
    match = NUMBER_WITH_UNIT[citation.field].fullmatch(citation.excerpt)
    return bool(match and Decimal(match.group(1)) == Decimal(str(value)))


def verify_protocol(protocol: ProtocolSpec) -> ProtocolVerification:
    """Check a synthetic text plan; local claims cannot promote source provenance."""
    failures: list[str] = []
    expected_ids = [f"step-{index + 1}" for index in range(len(protocol.steps))]
    actual_ids = [item.step_id for item in protocol.steps]
    if actual_ids != expected_ids:
        failures.append("step-order")
    if len(set(actual_ids)) != len(actual_ids):
        failures.append("duplicate-step-id")
    if protocol.min_temperature_c > protocol.max_temperature_c:
        failures.append("temperature-range-definition")
    total_volume = sum(Decimal(str(item.volume_ul)) for item in protocol.steps)
    if total_volume > Decimal(str(protocol.max_total_volume_ul)):
        failures.append("total-volume")

    documents = {document.document_id: document for document in protocol.documents}
    if len(documents) != len(protocol.documents):
        failures.append("duplicate-document-id")
    anchors: dict[tuple[str, str], tuple[int, int]] = {}
    source_step_ids: list[str] = []
    for document in protocol.documents:
        if sha256(document.text.encode("utf-8")).hexdigest() != document.text_sha256:
            failures.append(f"document-hash:{document.document_id}")
        if document.provenance_status == "blocked":
            failures.append(f"document-provenance:{document.document_id}")
        offset = 0
        for raw_line in document.text.splitlines(keepends=True):
            line = raw_line.removesuffix("\n")
            match = TEACHING_LINE.fullmatch(line)
            if match is None:
                failures.append(f"document-grammar:{document.document_id}:{offset}")
            else:
                source_step_ids.append(match.group("step_id"))
                key = (document.document_id, match.group("step_id"))
                if key in anchors:
                    failures.append(f"duplicate-source-step:{document.document_id}:{match.group('step_id')}")
                anchors[key] = (offset, offset + len(line))
            offset += len(raw_line)
    if Counter(source_step_ids) != Counter(actual_ids):
        failures.append("document-step-coverage")
    elif source_step_ids != actual_ids:
        failures.append("document-step-order")

    checked = 0
    used_spans: set[tuple[str, int, int]] = set()
    for step in protocol.steps:
        if step.action not in SAFE_ACTIONS or step.reagent not in SAFE_REAGENTS:
            failures.append(f"requires-expert-review:{step.step_id}")
        if not protocol.min_temperature_c <= step.temperature_c <= protocol.max_temperature_c:
            failures.append(f"temperature:{step.step_id}")
        counts = Counter(citation.field for citation in step.citations)
        for field in FIELDS:
            if counts[field] == 0:
                failures.append(f"missing-citation:{step.step_id}:{field}")
            elif counts[field] != 1:
                failures.append(f"duplicate-citation:{step.step_id}:{field}")
        for citation in step.citations:
            checked += 1
            key = (citation.document_id, citation.start, citation.end)
            if key in used_spans:
                failures.append(f"reused-citation:{step.step_id}:{citation.field}")
            used_spans.add(key)
            document = documents.get(citation.document_id)
            if document is None:
                failures.append(f"unknown-document:{step.step_id}:{citation.field}")
                continue
            if citation.start >= citation.end or citation.end > len(document.text) or document.text[citation.start:citation.end] != citation.excerpt:
                failures.append(f"citation-span:{step.step_id}:{citation.field}")
            anchor = anchors.get((citation.document_id, step.step_id))
            if anchor is None or not (anchor[0] <= citation.start < citation.end <= anchor[1]):
                failures.append(f"citation-step:{step.step_id}:{citation.field}")
            if citation.extraction_method != "exact":
                failures.append(f"inferred-citation:{step.step_id}:{citation.field}")
            if not _value_matches(step, citation):
                failures.append(f"citation-value:{step.step_id}:{citation.field}")
    passed = not failures
    return ProtocolVerification(
        passed=passed, failures=failures, checked_citations=checked,
        review_status="text-reviewed" if passed else "blocked",
        notes=[
            "The evaluator checks a bounded synthetic text fixture and declared constraints only.",
            "Source rights, real materials, equipment, safety, and human acceptance are unverified.",
            "It never schedules, controls, or authorizes wet-lab execution.",
        ],
    )
