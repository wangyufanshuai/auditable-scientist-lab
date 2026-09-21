"""Strict, side-effect-free domain contracts.

The models in this module deliberately contain no filesystem, network, solver, or LLM
behavior. They reject invalid state transitions at the boundary so later runtime code
cannot silently promote an unsupported scientific claim.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HASH_PATTERN = r"^[a-f0-9]{64}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ClaimStatus(StrEnum):
    CANDIDATE = "candidate"
    REPRODUCED = "reproduced"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"


class EvidenceLevel(StrEnum):
    DEMO = "demo"
    VALIDATED_REPRODUCTION = "validated-reproduction"
    REAL_DATA = "real-data"
    RESEARCH_CANDIDATE = "research-candidate"


class EvidenceKind(StrEnum):
    DATA = "data"
    FORMULA = "formula"
    CODE = "code"
    LOG = "log"
    EXTERNAL_REFERENCE = "external-reference"
    SNAPSHOT = "snapshot"


class RunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    UNVERIFIED = "unverified"


class ProvenanceStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    BLOCKED = "blocked"


class ResearchQuestion(StrictModel):
    question_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    observables: list[str] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    dataset_ref: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    intended_evidence_level: EvidenceLevel = EvidenceLevel.DEMO


class Hypothesis(StrictModel):
    hypothesis_id: str = Field(min_length=1)
    expression: str = Field(min_length=1)
    variables: list[str] = Field(min_length=1)
    units: dict[str, str] = Field(default_factory=dict)
    source: str = Field(min_length=1)
    status: ClaimStatus = ClaimStatus.CANDIDATE
    candidate_set_id: str = Field(min_length=1)
    train_split: str = Field(min_length=1)
    holdout_split: str | None = None
    complexity: int = Field(ge=1)
    failed_candidate_count: int = Field(default=0, ge=0)


class ExperimentPlan(StrictModel):
    plan_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    train_split: str = Field(min_length=1)
    holdout_split: str | None = None
    seed: int = Field(ge=0)
    tool_versions: dict[str, str] = Field(default_factory=dict)
    tolerances: dict[str, float] = Field(default_factory=dict)
    budget: dict[str, float | int] = Field(default_factory=dict)
    falsification_checks: list[str] = Field(min_length=1)
    candidate_set_commitment: str | None = Field(default=None, pattern=HASH_PATTERN)

    @model_validator(mode="after")
    def split_names_must_differ(self) -> "ExperimentPlan":
        if self.holdout_split is not None and self.holdout_split == self.train_split:
            raise ValueError("train_split and holdout_split must differ")
        return self


class Observation(StrictModel):
    observation_id: str = Field(min_length=1)
    dataset_hash: str = Field(pattern=HASH_PATTERN)
    split: str = Field(pattern=r"^(train|holdout|external)$")
    summary: dict[str, Any]
    units: dict[str, str] = Field(default_factory=dict)
    source_ref: str = Field(min_length=1)


class Evidence(StrictModel):
    evidence_id: str = Field(min_length=1)
    kind: EvidenceKind
    path_or_uri: str = Field(min_length=1)
    sha256: str = Field(pattern=HASH_PATTERN)
    source_revision: str = Field(min_length=1)
    provenance_status: ProvenanceStatus
    allowed_use: list[str] = Field(min_length=1)
    notes: str = ""


class Claim(StrictModel):
    text: str = Field(min_length=1)
    status: ClaimStatus = ClaimStatus.CANDIDATE
    level: EvidenceLevel | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    falsification_checks: list[str] = Field(min_length=1)
    holdout_verified: bool = False

    @model_validator(mode="after")
    def reproduced_requires_holdout(self) -> "Claim":
        if self.status == ClaimStatus.REPRODUCED and not self.holdout_verified:
            raise ValueError("a reproduced claim requires a verified holdout result")
        if self.status == ClaimStatus.REPRODUCED and not self.evidence_refs:
            raise ValueError("a reproduced claim requires evidence_refs")
        return self

    def promote_to_reproduced(self, *, holdout_evidence_ref: str) -> "Claim":
        """Return a promoted copy only when a concrete holdout evidence ref exists."""

        if not holdout_evidence_ref.strip():
            raise ValueError("holdout_evidence_ref cannot be empty")
        refs = list(dict.fromkeys([*self.evidence_refs, holdout_evidence_ref]))
        return self.model_copy(
            update={
                "status": ClaimStatus.REPRODUCED,
                "level": EvidenceLevel.VALIDATED_REPRODUCTION,
                "evidence_refs": refs,
                "holdout_verified": True,
            }
        )


class Agent(StrictModel):
    agent_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)


class Tool(StrictModel):
    tool_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    parameter_schema_ref: str = Field(min_length=1)
    deterministic: bool
    network_required: bool = False


class Memory(StrictModel):
    memory_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    version: str = Field(min_length=1)
    content_hash: str = Field(pattern=HASH_PATTERN)


class Evaluator(StrictModel):
    evaluator_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    read_only: bool = True


class Provider(StrictModel):
    provider_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)


class Policy(StrictModel):
    policy_id: str = Field(min_length=1)
    network: str = Field(pattern=r"^(disabled|allowlisted|unrestricted)$")
    max_seconds: float = Field(gt=0)
    max_tool_calls: int = Field(ge=0)
    allowed_paths: list[str] = Field(default_factory=list)
    allowed_providers: list[str] = Field(default_factory=list)


class Event(StrictModel):
    event_id: str = Field(min_length=1)
    seq: int = Field(ge=0)
    event_type: str = Field(min_length=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload_hash: str = Field(pattern=HASH_PATTERN)
    prev_event_hash: str = Field(pattern=r"^(genesis|[a-f0-9]{64})$")
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def timestamps_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class Trace(StrictModel):
    trace_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    input_hash: str = Field(pattern=HASH_PATTERN)
    entries: list[dict[str, Any]] = Field(default_factory=list)


class Run(StrictModel):
    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    input_hash: str = Field(pattern=HASH_PATTERN)
    code_revision: str = Field(min_length=1)
    environment: dict[str, Any]
    seed: int = Field(ge=0)
    evidence_refs: list[str] = Field(default_factory=list)
    status: RunStatus
    agent: Agent | None = None
    tools: list[Tool] = Field(default_factory=list)
    memories: list[Memory] = Field(default_factory=list)
    evaluators: list[Evaluator] = Field(default_factory=list)
    providers: list[Provider] = Field(default_factory=list)
    policy: Policy | None = None
    events: list[Event] = Field(default_factory=list)
    traces: list[Trace] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_event_chain_and_claim_refs(self) -> "Run":
        expected_refs = {item.evidence_id for item in self.evidence}
        if expected_refs and not set(self.evidence_refs).issubset(expected_refs):
            raise ValueError("run evidence_refs must resolve to evidence entries")
        if expected_refs:
            for claim in self.claims:
                unknown = set(claim.evidence_refs) - expected_refs
                if unknown:
                    raise ValueError(f"claim references unknown evidence: {sorted(unknown)}")
        for trace in self.traces:
            if trace.run_id != self.run_id or trace.input_hash != self.input_hash:
                raise ValueError("trace must reference its containing run and input hash")
        identifier_fields = {"tools": "tool_id", "memories": "memory_id", "evaluators": "evaluator_id", "providers": "provider_id"}
        for field_name, identifier_field in identifier_fields.items():
            records = getattr(self, field_name)
            ids = [getattr(item, identifier_field) for item in records]
            if len(ids) != len(set(ids)):
                raise ValueError(f"{field_name} must have unique identifiers")
        previous = "genesis"
        for expected_seq, event in enumerate(self.events):
            if event.seq != expected_seq:
                raise ValueError("event sequence must be contiguous starting at zero")
            if event.prev_event_hash != previous:
                raise ValueError("event hash chain is not contiguous")
            previous = event.payload_hash
        return self

    @classmethod
    def empty(
        cls,
        *,
        run_id: str,
        task_id: str,
        input_hash: str,
        code_revision: str,
        environment: dict[str, Any],
        seed: int,
    ) -> "Run":
        return cls(
            run_id=run_id,
            task_id=task_id,
            input_hash=input_hash,
            code_revision=code_revision,
            environment=environment,
            seed=seed,
            status=RunStatus.UNVERIFIED,
        )


__all__ = [
    "Agent",
    "Claim",
    "ClaimStatus",
    "Evidence",
    "EvidenceKind",
    "EvidenceLevel",
    "Event",
    "Evaluator",
    "ExperimentPlan",
    "Hypothesis",
    "Memory",
    "Observation",
    "Policy",
    "Provider",
    "ProvenanceStatus",
    "ResearchQuestion",
    "Run",
    "RunStatus",
    "StrictModel",
    "Tool",
    "Trace",
]
