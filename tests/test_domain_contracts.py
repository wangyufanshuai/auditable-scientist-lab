from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from auditable_scientist.domain import (
    Claim,
    ClaimStatus,
    Evidence,
    EvidenceKind,
    EvidenceLevel,
    Event,
    ExperimentPlan,
    Hypothesis,
    Observation,
    ResearchQuestion,
    Run,
    RunStatus,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "run.schema.json").read_text(encoding="utf-8"))
HASH = "a" * 64
HASH_B = "b" * 64


def evidence(evidence_id: str = "holdout-report") -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        kind=EvidenceKind.LOG,
        path_or_uri="artifacts/holdout.json",
        sha256=HASH,
        source_revision="snapshot-1",
        provenance_status="verified",
        allowed_use=["validated-reproduction"],
    )


def valid_run() -> Run:
    event = Event(
        event_id="event-0",
        seq=0,
        event_type="input",
        occurred_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
        payload_hash=HASH,
        prev_event_hash="genesis",
        payload={"question": "Hohmann transfer"},
    )
    return Run(
        run_id="run-1",
        task_id="t1-hohmann",
        created_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
        input_hash=HASH_B,
        code_revision="local-snapshot-1",
        environment={"python": "3.12.3"},
        seed=17,
        evidence_refs=["holdout-report"],
        status=RunStatus.UNVERIFIED,
        events=[event],
        claims=[
            Claim(
                text="Candidate matches the declared holdout within tolerance.",
                status=ClaimStatus.CANDIDATE,
                level=EvidenceLevel.DEMO,
                evidence_refs=["holdout-report"],
                falsification_checks=["dimension-check", "holdout-error"],
            )
        ],
        observations=[
            Observation(
                observation_id="obs-holdout",
                dataset_hash=HASH_B,
                split="holdout",
                summary={"rows": 4, "rmse": 0.0},
                units={"r1": "km", "r2": "km", "mu": "km^3/s^2"},
                source_ref="examples/hohmann/dataset.json",
            )
        ],
        evidence=[evidence()],
    )


def test_domain_models_cover_the_required_contracts() -> None:
    question = ResearchQuestion(
        question_id="rq-1",
        text="Recover a bounded Hohmann transfer observable.",
        domain="orbital-mechanics",
        observables=["time_of_flight_days"],
        assumptions=["circular coplanar two-body orbits"],
        dataset_ref="examples/hohmann/dataset.json",
        allowed_tools=["dimensional-check", "numeric-baseline"],
    )
    hypothesis = Hypothesis(
        hypothesis_id="h-1",
        expression="pi*sqrt(((r1+r2)/2)^3/mu)",
        variables=["r1", "r2", "mu"],
        units={"r1": "km", "r2": "km", "mu": "km^3/s^2"},
        source="bounded-generator",
        candidate_set_id="candidate-set-1",
        train_split="train-v1",
        holdout_split="holdout-v1",
        complexity=5,
    )
    plan = ExperimentPlan(
        plan_id="plan-1",
        question_id=question.question_id,
        train_split="train-v1",
        holdout_split="holdout-v1",
        seed=17,
        tool_versions={"numpy": "2.2.6"},
        tolerances={"rmse": 1e-9},
        budget={"max_candidates": 128, "max_seconds": 30},
        falsification_checks=["dimension-check", "holdout-error"],
        candidate_set_commitment=HASH,
    )
    assert question.domain == "orbital-mechanics"
    assert hypothesis.holdout_split == plan.holdout_split
    assert plan.seed == 17


def test_valid_run_matches_json_schema() -> None:
    payload = valid_run().model_dump(mode="json", exclude_none=True)
    Draft202012Validator(SCHEMA).validate(payload)


def test_claim_cannot_be_reproduced_without_holdout() -> None:
    with pytest.raises(ValidationError, match="verified holdout"):
        Claim(
            text="unsupported promotion",
            status=ClaimStatus.REPRODUCED,
            evidence_refs=["holdout-report"],
            falsification_checks=["holdout-error"],
        )


def test_claim_promotion_requires_and_records_holdout_evidence() -> None:
    claim = Claim(
        text="bounded candidate",
        status=ClaimStatus.CANDIDATE,
        evidence_refs=["train-report"],
        falsification_checks=["holdout-error"],
    )
    promoted = claim.promote_to_reproduced(holdout_evidence_ref="holdout-report")
    assert promoted.status == ClaimStatus.REPRODUCED
    assert promoted.holdout_verified is True
    assert promoted.level == EvidenceLevel.VALIDATED_REPRODUCTION
    assert promoted.evidence_refs == ["train-report", "holdout-report"]


def test_run_rejects_unknown_claim_evidence() -> None:
    run = valid_run().model_dump(mode="python")
    run["claims"][0]["evidence_refs"] = ["does-not-exist"]
    with pytest.raises(ValidationError, match="unknown evidence"):
        Run.model_validate(run)


def test_run_rejects_broken_event_sequence_or_chain() -> None:
    run = valid_run().model_dump(mode="python")
    run["events"][0]["seq"] = 4
    with pytest.raises(ValidationError, match="contiguous"):
        Run.model_validate(run)


def test_models_reject_malformed_hashes_and_same_split_names() -> None:
    with pytest.raises(ValidationError):
        Observation(
            observation_id="obs-1",
            dataset_hash="not-a-sha256",
            split="holdout",
            summary={"rows": 1},
            source_ref="fixture",
        )
    with pytest.raises(ValidationError, match="must differ"):
        ExperimentPlan(
            plan_id="plan-1",
            question_id="rq-1",
            train_split="same",
            holdout_split="same",
            seed=1,
            falsification_checks=["check"],
        )
