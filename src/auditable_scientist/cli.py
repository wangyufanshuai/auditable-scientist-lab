"""Offline CLI for the auditable Hohmann vertical slice."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .benchmark import HohmannConfig, load_hohmann_config, load_hohmann_dataset, make_hohmann_study, run_hohmann_experiment
from .adapters import Project05Adapter
from .domain import (
    Agent,
    Claim,
    ClaimStatus,
    Evidence,
    EvidenceKind,
    EvidenceLevel,
    Evaluator,
    Memory,
    Observation,
    Policy,
    ProvenanceStatus,
    Provider,
    Run,
    RunStatus,
    Trace,
    Tool,
)
from .policy import ToolRegistry
from .reporting import render_hohmann_report
from .runtime.canonical import canonical_hash, canonical_json
from .runtime.environment import capture_environment
from .runtime.event_log import EventLog
from .runtime.replay import ReplayManifest, ReplayMismatch, fingerprint_file
from .runtime.run_integrity import verify_run_record


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _resolve_dataset(config_path: Path, dataset_path: str) -> Path:
    candidates = [Path(dataset_path), config_path.parent / dataset_path]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"dataset file not found: {dataset_path}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _source_paths() -> list[Path]:
    root = _repo_root()
    return [
        root / "src/auditable_scientist/benchmark/hohmann.py",
        root / "src/auditable_scientist/benchmark/study.py",
        root / "src/auditable_scientist/tools/dimensions.py",
        root / "src/auditable_scientist/tools/errors.py",
        root / "src/auditable_scientist/tools/numerical.py",
        root / "src/auditable_scientist/runtime/canonical.py",
        root / "src/auditable_scientist/cli.py",
        root / "src/auditable_scientist/policy/runtime.py",
        root / "src/auditable_scientist/domain/models.py",
        root / "schemas/run.schema.json",
        root / "docs/EVIDENCE_POLICY.md",
        root / "src/auditable_scientist/adapters/project05.py",
        root / "src/auditable_scientist/runtime/run_integrity.py",
        root / "schemas/hohmann-tool-call-v1.json",
    ]


def _evidence(evidence_id: str, kind: EvidenceKind, path: Path, *, allowed_use: list[str]) -> Evidence:
    fingerprint = fingerprint_file(path)
    return Evidence(
        evidence_id=evidence_id,
        kind=kind,
        path_or_uri=str(path),
        sha256=fingerprint.sha256,
        source_revision="local-working-tree",
        provenance_status=ProvenanceStatus.UNVERIFIED,
        allowed_use=allowed_use,
        notes="Local source or fixture; replay verifies bytes but does not establish external licensing or real-data status.",
    )


def _build_run(config_path: Path, *, seed: int, output_dir: Path, offline: bool) -> Path:
    config = load_hohmann_config(config_path)
    dataset_path = _resolve_dataset(config_path, config.dataset_path)
    cases = load_hohmann_dataset(dataset_path)
    policy = Policy(
        policy_id="offline-hohmann-v1",
        network="disabled",
        max_seconds=60,
        max_tool_calls=1,
        allowed_paths=[str(dataset_path.parent), str(_repo_root())],
        allowed_providers=["internal-bounded-generator"],
    )
    registry = ToolRegistry(policy)
    argument_schema_path = _repo_root() / "schemas/hohmann-tool-call-v1.json"
    hohmann_tool = Tool(
            tool_id="hohmann-benchmark",
            name="Hohmann benchmark",
            version="1",
            parameter_schema_ref="schemas/hohmann-tool-call-v1.json",
            deterministic=True,
            network_required=False,
        )
    registry.register(
        hohmann_tool,
        lambda _: run_hohmann_experiment(config, cases),
        argument_schema=json.loads(argument_schema_path.read_text(encoding="utf-8")),
    )
    experiment = registry.invoke(
        "hohmann-benchmark",
        {"task_id": config.task_id},
        path_refs=[str(dataset_path)],
        provider_id="internal-bounded-generator",
    )
    study = make_hohmann_study(config, experiment, dataset_path=dataset_path, seed=seed)
    input_payload = {"config": config.model_dump(mode="json"), "cases": [case.model_dump(mode="json") for case in cases], "seed": seed}
    input_hash = canonical_hash(input_payload)
    run_id = f"run-{input_hash[:16]}"
    run_dir = output_dir / run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"run directory already exists; choose another output directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    _json_dump(run_dir / "input.json", input_payload)

    dataset_evidence = _evidence("ev-hohmann-dataset", EvidenceKind.DATA, dataset_path, allowed_use=["offline-demo", "fixture"])
    code_evidence = _evidence(
        "ev-hohmann-baseline-code",
        EvidenceKind.CODE,
        _repo_root() / "src/auditable_scientist/tools/numerical.py",
        allowed_use=["analytic-reference", "offline-demo"],
    )
    evidence = [dataset_evidence, code_evidence]
    project05_snapshot = Project05Adapter().snapshot()
    project05_snapshot_path = run_dir / "project05-snapshot.json"
    _json_dump(project05_snapshot_path, project05_snapshot.model_dump(mode="json"))
    if project05_snapshot.status != "blocked":
        evidence.append(
            _evidence(
                "ev-project05-source-snapshot",
                EvidenceKind.SNAPSHOT,
                project05_snapshot_path,
                allowed_use=["source-provenance", "offline-demo"],
            )
        )
    agent = Agent(
        agent_id="offline-bounded-agent-v1",
        name="Offline bounded research agent",
        version="1",
        capabilities=["propose-hypothesis", "invoke-registered-tool", "explain-result"],
    )
    memory_source = _repo_root() / "docs/EVIDENCE_POLICY.md"
    memory = Memory(
        memory_id="evidence-policy-memory-v1",
        source_ref=str(memory_source),
        scope="claim-level evidence boundaries",
        version="local-snapshot",
        content_hash=fingerprint_file(memory_source).sha256,
    )
    evaluator = Evaluator(
        evaluator_id="hohmann-holdout-v1",
        name="Hohmann dimensional and holdout evaluator",
        version="1",
        read_only=True,
    )
    provider = Provider(
        provider_id="internal-bounded-generator",
        kind="symbolic-candidate-generator",
        name="Internal bounded candidate generator",
        version="1",
        source_ref="src/auditable_scientist/benchmark/hohmann.py",
    )
    train_ids = [case.case_id for case in cases if case.split == "train"]
    holdout_ids = [case.case_id for case in cases if case.split == "holdout"]
    observations = [
        Observation(
            observation_id="obs-train",
            dataset_hash=experiment.dataset_hash,
            split="train",
            summary={"case_ids": train_ids, "target": config.target, "count": len(train_ids)},
            units={"r1_km": "km", "r2_km": "km", "mu_km3_s2": "km^3/s^2", "target": "day"},
            source_ref=str(dataset_path),
        ),
        Observation(
            observation_id="obs-holdout",
            dataset_hash=experiment.dataset_hash,
            split="holdout",
            summary={"case_ids": holdout_ids, "target": config.target, "count": len(holdout_ids)},
            units={"r1_km": "km", "r2_km": "km", "mu_km3_s2": "km^3/s^2", "target": "day"},
            source_ref=str(dataset_path),
        ),
    ]
    claim_status = ClaimStatus.REPRODUCED if experiment.gate.passed else ClaimStatus.CANDIDATE
    claim = Claim(
        text=(
            "Within the committed analytic Hohmann fixture, the bounded candidate "
            f"{experiment.selected_candidate_id} passes the dimensional and fixed holdout gates."
        ),
        status=claim_status,
        level=EvidenceLevel.VALIDATED_REPRODUCTION if experiment.gate.passed else EvidenceLevel.DEMO,
        evidence_refs=[item.evidence_id for item in evidence],
        falsification_checks=["dimensional-consistency", "fixed-holdout-rmse", "candidate-set-replay"],
        holdout_verified=experiment.gate.passed,
    )
    environment = capture_environment(["auditable-scientist-lab", "pydantic", "sympy"])
    run = Run(
        run_id=run_id,
        task_id=config.task_id,
        input_hash=input_hash,
        code_revision=config.source_revision,
        environment={**environment, "network": "disabled" if offline else "not-requested"},
        seed=seed,
        evidence_refs=[item.evidence_id for item in evidence],
        status=RunStatus.COMPLETED if experiment.gate.passed else RunStatus.UNVERIFIED,
        agent=agent,
        tools=[hohmann_tool],
        memories=[memory],
        evaluators=[evaluator],
        providers=[provider],
        policy=policy,
        claims=[claim],
        observations=observations,
        evidence=evidence,
    )
    event_log = EventLog(run_dir / "events.jsonl")
    event_log.append("run.initialized", {"run_id": run_id, "input_hash": input_hash})
    event_log.append(
        "plan.created",
        {
            "plan_id": study["experiment_plan"]["plan_id"],
            "question_id": study["experiment_plan"]["question_id"],
            "train_split": study["experiment_plan"]["train_split"],
            "holdout_split": study["experiment_plan"]["holdout_split"],
            "seed": study["experiment_plan"]["seed"],
        },
    )
    event_log.append(
        "policy.applied",
        {
            "policy_id": policy.policy_id,
            "network": policy.network,
            "max_seconds": policy.max_seconds,
            "max_tool_calls": policy.max_tool_calls,
            "allowed_provider": "internal-bounded-generator",
        },
    )
    event_log.append(
        "data.summarized",
        {
            "dataset_hash": experiment.dataset_hash,
            "evidence_id": dataset_evidence.evidence_id,
            "train_count": len(train_ids),
            "holdout_count": len(holdout_ids),
        },
    )
    event_log.append("tool.invoked", {"tool_id": "hohmann-benchmark", "calls_used": registry.calls_used})
    event_log.append(
        "candidate_set.committed",
        {"candidate_order": experiment.candidate_order, "candidate_set_hash": experiment.candidate_set_hash},
    )
    event_log.append(
        "holdout.evaluated",
        {"selected_candidate_id": experiment.selected_candidate_id, "gate": experiment.gate.model_dump(mode="json")},
    )
    event_log.append(
        "calculation.completed",
        {
            "selected_candidate_id": experiment.selected_candidate_id,
            "train_rmse": experiment.gate.train.rmse,
            "holdout_rmse": experiment.gate.holdout.rmse,
        },
    )
    event_log.append(
        "failure.checked",
        {"failures": [] if experiment.gate.passed else ["holdout-gate-failed"], "gate_passed": experiment.gate.passed},
    )
    event_log.append(
        "approval.recorded",
        {"decision": "not-required", "scope": "offline-fixture", "human_approval": False},
    )
    event_log.append("run.completed", {"status": run.status.value, "claim_status": claim.status.value})
    events = event_log.verify()
    run = run.model_copy(
        update={
            "events": events,
            "traces": [
                Trace(
                    trace_id=f"trace-{run_id}",
                    run_id=run_id,
                    input_hash=input_hash,
                    entries=[
                        {"seq": event.seq, "event_type": event.event_type, "payload_hash": event.payload_hash}
                        for event in events
                    ],
                )
            ],
        }
    )
    dataset_source = dataset_path
    manifest = ReplayManifest.create(
        input_payload=input_payload,
        code_revision=config.source_revision,
        environment=environment,
        seed=seed,
        source_paths=[*_source_paths(), dataset_source],
        evidence_paths=[dataset_source, _repo_root() / "src/auditable_scientist/tools/numerical.py", project05_snapshot_path],
        candidate_order=experiment.candidate_order,
        computational_output=experiment.model_dump(mode="json"),
    )
    _json_dump(run_dir / "run.json", run.model_dump(mode="json"))
    _json_dump(run_dir / "experiment.json", experiment.model_dump(mode="json"))
    _json_dump(run_dir / "study.json", study)
    manifest.computational_output = {"experiment": experiment.model_dump(mode="json"), "study": study}
    manifest.write(run_dir / "replay-manifest.json")
    report = render_hohmann_report(run=run.model_dump(mode="json"), experiment=experiment.model_dump(mode="json"))
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    return run_dir


def _replay(run_dir: Path) -> dict[str, Any]:
    input_payload = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    config = HohmannConfig.model_validate(input_payload["config"])
    from .benchmark.hohmann import HohmannCase

    typed_cases = [HohmannCase.model_validate(item) for item in input_payload["cases"]]
    experiment = run_hohmann_experiment(config, typed_cases)
    from .benchmark import make_hohmann_study

    dataset_path = Path(config.dataset_path)
    if not dataset_path.is_absolute():
        dataset_path = (_repo_root() / dataset_path).resolve()
    if not dataset_path.is_file():
        raise FileNotFoundError(f"dataset file not found during replay: {dataset_path}")
    study = make_hohmann_study(config, experiment, dataset_path=dataset_path, seed=input_payload["seed"])
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    receipt = manifest.verify(
        input_payload=input_payload,
        code_revision=config.source_revision,
        environment=capture_environment(["auditable-scientist-lab", "pydantic", "sympy"]),
        seed=input_payload["seed"],
        source_paths=[item.path for item in manifest.source_files],
        evidence_paths=[item.path for item in manifest.evidence_files],
        candidate_order=experiment.candidate_order,
        computational_output={"experiment": experiment.model_dump(mode="json"), "study": study},
    )
    saved_experiment = json.loads((run_dir / "experiment.json").read_text(encoding="utf-8"))
    saved_study = json.loads((run_dir / "study.json").read_text(encoding="utf-8"))
    if canonical_hash(saved_experiment) != canonical_hash(experiment.model_dump(mode="json")):
        raise ReplayMismatch("saved experiment differs from deterministic replay")
    if canonical_hash(saved_study) != canonical_hash(study):
        raise ReplayMismatch("saved study differs from deterministic replay")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl", root=_repo_root())
    if run.input_hash != manifest.input_hash or run.seed != manifest.seed or run.code_revision != manifest.code_revision:
        raise ReplayMismatch("saved Run identity differs from replay manifest")
    if run.status.value != ("completed" if experiment.gate.passed else "unverified"):
        raise ReplayMismatch("saved Run status differs from holdout gate")
    if len(run.claims) != 1 or run.claims[0].holdout_verified != experiment.gate.passed:
        raise ReplayMismatch("saved claim differs from holdout gate")
    events_by_type = {event.event_type: event for event in run.events}
    required_events = {"run.initialized", "plan.created", "policy.applied", "data.summarized", "tool.invoked", "candidate_set.committed", "holdout.evaluated", "calculation.completed", "failure.checked", "approval.recorded", "run.completed"}
    if not required_events.issubset(events_by_type):
        raise ReplayMismatch("saved Run is missing a required lifecycle event")
    if events_by_type["candidate_set.committed"].payload != {
        "candidate_order": experiment.candidate_order,
        "candidate_set_hash": experiment.candidate_set_hash,
    }:
        raise ReplayMismatch("candidate-set event differs from deterministic replay")
    if events_by_type["holdout.evaluated"].payload != {
        "selected_candidate_id": experiment.selected_candidate_id,
        "gate": experiment.gate.model_dump(mode="json"),
    }:
        raise ReplayMismatch("holdout event differs from deterministic replay")
    updated = render_hohmann_report(run=run.model_dump(mode="json"), experiment=experiment.model_dump(mode="json"), receipt=receipt.model_dump(mode="json"))
    (run_dir / "report.md").write_text(updated, encoding="utf-8")
    return receipt.model_dump(mode="json")


def _init(path: Path) -> Path:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing config: {path}")
    template = {
        "schema_version": "hohmann-config-v1",
        "task_id": "hohmann-time-of-flight-v1",
        "dataset_path": "examples/hohmann/dataset.json",
        "target": "time_of_flight_days",
        "max_holdout_rmse": 1e-8,
        "source_revision": "local-working-tree",
    }
    _json_dump(path, template)
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auditable-scientist")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="write a Hohmann run configuration")
    init_parser.add_argument("path", type=Path)
    run_parser = subparsers.add_parser("run", help="execute the offline Hohmann benchmark")
    run_parser.add_argument("config", type=Path)
    run_parser.add_argument("--offline", action="store_true", help="record that network access is disabled")
    run_parser.add_argument("--seed", type=int, default=17)
    run_parser.add_argument("--output-dir", type=Path, default=Path("artifacts/runs"))
    for name in ("replay", "inspect", "export-report"):
        command_parser = subparsers.add_parser(name)
        command_parser.add_argument("run_dir", type=Path)
        if name == "export-report":
            command_parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            print(_init(args.path))
        elif args.command == "run":
            print(_build_run(args.config, seed=args.seed, output_dir=args.output_dir, offline=args.offline))
        elif args.command == "replay":
            print(json.dumps(_replay(args.run_dir), indent=2, sort_keys=True))
        elif args.command == "inspect":
            run = json.loads((args.run_dir / "run.json").read_text(encoding="utf-8"))
            experiment = json.loads((args.run_dir / "experiment.json").read_text(encoding="utf-8"))
            print(json.dumps({"run_id": run["run_id"], "status": run["status"], "claim": run["claims"][0], "selected_candidate_id": experiment["selected_candidate_id"], "holdout": experiment["gate"]}, indent=2, sort_keys=True))
        elif args.command == "export-report":
            source = args.run_dir / "report.md"
            destination = args.output or source
            if destination.resolve() != source.resolve():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            print(destination)
        return 0
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
