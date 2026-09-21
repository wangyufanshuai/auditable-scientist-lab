"""Concrete T1 study records built from the deterministic Hohmann experiment."""

from __future__ import annotations

from pathlib import Path

from ..domain import ExperimentPlan, Hypothesis, ResearchQuestion
from .hohmann import HohmannConfig, HohmannExperiment


def make_hohmann_study(
    config: HohmannConfig,
    experiment: HohmannExperiment,
    *,
    dataset_path: Path,
    seed: int,
) -> dict[str, dict]:
    selected = next(item for item in experiment.candidates if item.candidate_id == experiment.selected_candidate_id)
    question = ResearchQuestion(
        question_id="rq-hohmann-time-of-flight-v1",
        text="Can a bounded symbolic candidate search recover the heliocentric Hohmann transfer time-of-flight expression within a fixed holdout and dimensional gate?",
        domain="orbital-mechanics",
        observables=[config.target],
        assumptions=["circular coplanar heliocentric orbits", "two-body dynamics", "analytic fixture is the declared reference"],
        dataset_ref=str(dataset_path),
        allowed_tools=["dimensional-check-v1", "hohmann-analytic-v1", "error-statistics-v1", "internal-bounded-generator"],
        intended_evidence_level="validated-reproduction",
    )
    hypothesis = Hypothesis(
        hypothesis_id=selected.candidate_id,
        expression=selected.expression,
        variables=["r1", "r2", "mu"],
        units={"r1": "km", "r2": "km", "mu": "km^3/s^2", "target": "day"},
        source=selected.source,
        status="reproduced" if experiment.gate.passed else "candidate",
        candidate_set_id=experiment.candidate_set_hash,
        train_split="train",
        holdout_split="holdout",
        complexity=selected.complexity,
        failed_candidate_count=selected.failed_candidate_count,
    )
    plan = ExperimentPlan(
        plan_id="plan-hohmann-time-of-flight-v1",
        question_id=question.question_id,
        train_split="train",
        holdout_split="holdout",
        seed=seed,
        tool_versions={
            "dimensional-check": "v1",
            "hohmann-analytic": "v1",
            "error-statistics": "v1",
            "internal-bounded-generator": "v1",
        },
        tolerances={"max_holdout_rmse_days": config.max_holdout_rmse},
        budget={"max_candidates": len(experiment.candidate_order), "max_tool_calls": 1},
        falsification_checks=["dimensional-consistency", "fixed-holdout-rmse", "candidate-set-replay", "source-snapshot"],
        candidate_set_commitment=experiment.candidate_set_hash,
    )
    return {
        "research_question": question.model_dump(mode="json"),
        "hypothesis": hypothesis.model_dump(mode="json"),
        "experiment_plan": plan.model_dump(mode="json"),
    }
