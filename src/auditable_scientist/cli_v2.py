"""Versioned offline CLI: analytic discovery and RK4 propagation in one Run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from . import cli as legacy_cli
from .benchmark import HohmannConfig, load_hohmann_config, load_hohmann_dataset, make_hohmann_study, run_hohmann_experiment
from .benchmark.hohmann import HohmannCase, HohmannExperiment
from .domain import (
    Agent, Claim, ClaimStatus, Evidence, EvidenceKind, EvidenceLevel,
    Evaluator, ExperimentPlan, Hypothesis, Memory, Observation, Policy,
    ProvenanceStatus, Provider, ResearchQuestion, Run, RunStatus, Tool, Trace,
)
from .policy import ToolRegistry
from .runtime.canonical import canonical_hash, canonical_json
from .runtime.environment import capture_environment
from .runtime.event_log import EventLog
from .runtime.paths import installation_revision, project_root, resource_path, source_path
from .runtime.replay import BoundPaths, ReplayManifest, ReplayMismatch, fingerprint_file
from .runtime.run_integrity import verify_run_record
from .tools.orbit_audit_v2 import evaluate_orbit_grid


ANALYTIC_PROVIDER = "internal-bounded-generator"
NUMERICAL_PROVIDER = "internal-rk4-t1-orbit-v2"
ANALYTIC_TOOL = "hohmann-benchmark-v2"
NUMERICAL_TOOL = "t1-rk4-orbit-v2"
EVENT_TYPES = (
    "run.initialized", "policy.applied", "tool.invoked", "tool.invoked",
    "candidate_set.committed", "holdout.evaluated", "numerical.evaluated",
    "negative_case.checked", "run.completed",
)


def _source_paths() -> list[Path]:
    modules = (
        "__main__.py", "cli_v2.py", "cli.py", "benchmark/hohmann.py",
        "benchmark/study.py", "tools/dimensions.py", "tools/errors.py",
        "tools/numerical.py", "tools/orbit_integrator.py", "tools/orbit_audit_v2.py",
        "domain/models.py", "policy/runtime.py", "runtime/canonical.py",
        "runtime/environment.py", "runtime/event_log.py", "runtime/replay.py",
        "runtime/run_integrity.py", "runtime/paths.py",
    )
    resources = (
        "schemas/hohmann-tool-call-v1.json", "docs/EVIDENCE_POLICY.md",
        "docs/T1_SYMBOLIC_GRAMMAR.md",
    )
    return [
        *[source_path(f"src/auditable_scientist/{module}") for module in modules],
        *[resource_path(name) for name in resources],
    ]


def _policy(dataset: Path) -> Policy:
    return Policy(
        policy_id="offline-hohmann-combined-v2", network="disabled",
        max_seconds=120, max_tool_calls=2, allowed_paths=[str(dataset.resolve())],
        allowed_providers=[ANALYTIC_PROVIDER, NUMERICAL_PROVIDER],
    )


def _tools() -> list[Tool]:
    return [
        Tool(tool_id=ANALYTIC_TOOL, name="Bounded Hohmann candidate evaluator", version="2",
             parameter_schema_ref="schemas/hohmann-tool-call-v1.json", deterministic=True),
        Tool(tool_id=NUMERICAL_TOOL, name="Offline RK4 two-body propagator", version="2",
             parameter_schema_ref="schemas/hohmann-tool-call-v1.json", deterministic=True),
    ]


def _compute(config: HohmannConfig, cases: list[HohmannCase], dataset: Path) -> tuple[HohmannExperiment, dict]:
    registry = ToolRegistry(_policy(dataset))
    schema = json.loads(resource_path("schemas/hohmann-tool-call-v1.json").read_text(encoding="utf-8"))
    analytic, numerical = _tools()
    registry.register(analytic, lambda _arguments: run_hohmann_experiment(config, cases), argument_schema=schema)
    registry.register(numerical, lambda _arguments: evaluate_orbit_grid(cases), argument_schema=schema)
    arguments = {"task_id": config.task_id}
    experiment = registry.invoke(
        ANALYTIC_TOOL, arguments, path_refs=[str(dataset)], provider_id=ANALYTIC_PROVIDER,
    )
    orbit = registry.invoke(
        NUMERICAL_TOOL, arguments, path_refs=[str(dataset)], provider_id=NUMERICAL_PROVIDER,
    )
    if registry.calls_used != 2 or orbit["case_count"] != len(cases):
        raise ReplayMismatch("versioned T1 Run did not execute both registered tools")
    return experiment, orbit


def _study(config: HohmannConfig, experiment: HohmannExperiment, orbit: dict, *, dataset_ref: str, seed: int) -> dict:
    study = make_hohmann_study(config, experiment, dataset_path=dataset_ref, seed=seed)
    study["research_question"]["allowed_tools"].append(NUMERICAL_TOOL)
    study["experiment_plan"]["tool_versions"][NUMERICAL_TOOL] = "v2"
    study["experiment_plan"]["budget"]["max_tool_calls"] = 2
    study["experiment_plan"]["falsification_checks"].extend([
        "event-detected-apoapsis", "step-refinement", "repulsive-force-negative",
    ])
    if not all(orbit["checks"].values()):
        study["hypothesis"]["status"] = "candidate"
    ResearchQuestion.model_validate(study["research_question"])
    Hypothesis.model_validate(study["hypothesis"])
    ExperimentPlan.model_validate(study["experiment_plan"])
    return study


def _environment() -> dict[str, Any]:
    return {
        **capture_environment(["auditable-scientist-lab", "pydantic", "sympy", "jsonschema"]),
        "network": "disabled", "runtime": "t1-combined-cli-v2",
        "providers": [ANALYTIC_PROVIDER, NUMERICAL_PROVIDER],
    }


def _evidence(evidence_id: str, kind: EvidenceKind, path: Path, bindings: BoundPaths,
              allowed_use: list[str]) -> Evidence:
    return Evidence(
        evidence_id=evidence_id, kind=kind, path_or_uri=bindings.ref(path),
        sha256=fingerprint_file(path).sha256, source_revision=installation_revision(),
        provenance_status=ProvenanceStatus.UNVERIFIED, allowed_use=allowed_use,
        notes="Local source or declared fixture; hashes verify bytes, not real-data rights or mission validity.",
    )


def _run_record(config: HohmannConfig, cases: list[HohmannCase], experiment: HohmannExperiment,
                orbit: dict, *, input_hash: str, seed: int, run_dir: Path,
                events: list) -> Run:
    bindings = BoundPaths(root=project_root(), run_dir=run_dir)
    dataset = run_dir / "dataset.json"
    analytic_code = source_path("src/auditable_scientist/benchmark/hohmann.py")
    numerical_code = source_path("src/auditable_scientist/tools/orbit_audit_v2.py")
    evidence = [
        _evidence("ev-t1-v2-dataset", EvidenceKind.DATA, dataset, bindings, ["synthetic-fixture"]),
        _evidence("ev-t1-v2-analytic-code", EvidenceKind.CODE, analytic_code, bindings, ["bounded-candidate-generator"]),
        _evidence("ev-t1-v2-numerical-code", EvidenceKind.CODE, numerical_code, bindings, ["independent-time-propagation"]),
    ]
    combined_pass = experiment.gate.passed and all(orbit["checks"].values())
    run_id = f"run-t1-v2-{input_hash[:16]}"
    memory_source = resource_path("docs/EVIDENCE_POLICY.md")
    traces = [Trace(
        trace_id=f"trace-{run_id}", run_id=run_id, input_hash=input_hash,
        entries=[{"seq": event.seq, "event_type": event.event_type, "payload_hash": event.payload_hash}
                 for event in events],
    )]
    return Run(
        run_id=run_id, task_id=config.task_id, input_hash=input_hash,
        code_revision=config.source_revision, environment=_environment(), seed=seed,
        evidence_refs=[item.evidence_id for item in evidence],
        status=RunStatus.COMPLETED if combined_pass else RunStatus.UNVERIFIED,
        agent=Agent(agent_id="offline-t1-combined-agent-v2", name="Offline Hohmann research agent",
                    version="2", capabilities=["enumerate-bounded-candidates", "invoke-rk4-propagator"]),
        tools=_tools(),
        memories=[Memory(
            memory_id="evidence-policy-memory-v1", source_ref=bindings.ref(memory_source),
            scope="claim-level evidence boundaries", version="local-snapshot",
            content_hash=fingerprint_file(memory_source).sha256,
        )],
        evaluators=[
            Evaluator(evaluator_id="hohmann-holdout-v2", name="T1 dimensional and fixed holdout evaluator", version="2"),
            Evaluator(evaluator_id="t1-orbit-refinement-v2", name="T1 two-body propagation evaluator", version="2"),
        ],
        providers=[
            Provider(provider_id=ANALYTIC_PROVIDER, kind="symbolic-candidate-generator",
                     name="Internal bounded candidate generator", version="2",
                     source_ref="src/auditable_scientist/benchmark/hohmann.py"),
            Provider(provider_id=NUMERICAL_PROVIDER, kind="deterministic-numerical-backend",
                     name="Internal RK4 orbit propagator", version="2",
                     source_ref="src/auditable_scientist/tools/orbit_audit_v2.py"),
        ],
        policy=_policy(dataset).model_copy(update={"allowed_paths": [bindings.ref(dataset)]}),
        events=events, traces=traces,
        claims=[
            Claim(
                text="Within this declared circular two-body fixture, the selected expression passes the fixed holdout and independent propagation gates.",
                status=ClaimStatus.REPRODUCED if combined_pass else ClaimStatus.CANDIDATE,
                level=EvidenceLevel.VALIDATED_REPRODUCTION if combined_pass else EvidenceLevel.DEMO,
                evidence_refs=[item.evidence_id for item in evidence],
                falsification_checks=["dimensional-consistency", "fixed-holdout-rmse",
                                      "event-detected-apoapsis", "step-refinement", "repulsive-force-negative"],
                holdout_verified=combined_pass,
            ),
            Claim(
                text="The idealized calculation predicts a dated Mars mission trajectory.",
                status=ClaimStatus.UNVERIFIED, level=EvidenceLevel.DEMO,
                evidence_refs=[item.evidence_id for item in evidence],
                falsification_checks=["dated-ephemeris", "encounter-geometry", "rights-review"],
                holdout_verified=False,
            ),
        ],
        observations=[
            Observation(
                observation_id="obs-t1-v2-train", dataset_hash=experiment.dataset_hash, split="train",
                summary={"case_ids": [case.case_id for case in cases if case.split == "train"]},
                units={"radius": "km", "time_of_flight": "day"}, source_ref=bindings.ref(dataset),
            ),
            Observation(
                observation_id="obs-t1-v2-holdout", dataset_hash=experiment.dataset_hash, split="holdout",
                summary={"case_ids": [case.case_id for case in cases if case.split == "holdout"]},
                units={"radius": "km", "time_of_flight": "day"}, source_ref=bindings.ref(dataset),
            ),
        ],
        evidence=evidence,
    )


def _event_payloads(run_id: str, input_hash: str, experiment: HohmannExperiment,
                    orbit: dict, status: RunStatus) -> list[dict[str, Any]]:
    return [
        {"run_id": run_id, "input_hash": input_hash},
        {"policy_id": "offline-hohmann-combined-v2", "network": "disabled", "max_tool_calls": 2},
        {"tool_id": ANALYTIC_TOOL, "provider_id": ANALYTIC_PROVIDER, "calls_used": 1},
        {"tool_id": NUMERICAL_TOOL, "provider_id": NUMERICAL_PROVIDER, "calls_used": 2},
        {"candidate_order": experiment.candidate_order, "candidate_set_hash": experiment.candidate_set_hash},
        {"selected_candidate_id": experiment.selected_candidate_id, "gate": experiment.gate.model_dump(mode="json")},
        {"summary": orbit["summary"], "checks": orbit["checks"], "case_count": orbit["case_count"]},
        {"repulsive_force_rejected": orbit["checks"]["repulsive_force_rejected"]},
        {"status": status.value},
    ]


def _report(run: Run, experiment: HohmannExperiment, orbit: dict, receipt: dict | None = None) -> str:
    gate = experiment.gate
    return (
        "# Auditable Scientist Lab — T1 combined Run v2\n\n"
        f"- Run: `{run.run_id}`; status: `{run.status.value}`\n"
        f"- Selected candidate: `{experiment.selected_candidate_id}`\n"
        f"- Fixed holdout RMSE: `{gate.holdout.rmse}` days; threshold: `{gate.threshold}` days\n"
        f"- Numerical backend: `internal-rk4-t1-orbit-v2`; cases: `{orbit['case_count']}`\n"
        f"- Maximum relative TOF error: `{orbit['summary']['relative_tof_error']}`\n"
        f"- Maximum relative position error: `{orbit['summary']['relative_final_position_error']}`\n"
        f"- Numerical gates: `{orbit['checks']}`\n"
        f"- Synthetic-fixture Claim: `{run.claims[0].status.value}` at `{run.claims[0].level.value}`\n"
        f"- Mission Claim: `{run.claims[1].status.value}` at `{run.claims[1].level.value}`\n"
        f"- Replay: `{receipt['verified'] if receipt else 'pending'}`\n\n"
        "The departure state uses analytic vis-viva. This checks only bounded time propagation "
        "within synthetic circular two-body assumptions. Dated ephemerides, source rights, mission "
        "geometry, novelty, and publication review remain open.\n"
    )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")


def build_run(config_path: Path, *, seed: int, output_dir: Path) -> Path:
    if seed < 0:
        raise ValueError("seed must be nonnegative")
    config = load_hohmann_config(config_path)
    original_dataset = legacy_cli._resolve_dataset(config_path, config.dataset_path)
    cases = load_hohmann_dataset(original_dataset)
    portable_config = config.model_copy(update={"dataset_path": "run://dataset.json"})
    input_payload = {
        "schema_version": "t1-cli-run-input-v2",
        "config": portable_config.model_dump(mode="json"),
        "cases": [case.model_dump(mode="json") for case in cases],
        "seed": seed,
    }
    input_hash = canonical_hash(input_payload)
    run_id = f"run-t1-v2-{input_hash[:16]}"
    run_dir = (output_dir / run_id).resolve()
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    dataset = run_dir / "dataset.json"
    shutil.copyfile(original_dataset, dataset)
    if canonical_hash([case.model_dump(mode="json") for case in load_hohmann_dataset(dataset)]) != canonical_hash(input_payload["cases"]):
        raise ReplayMismatch("dataset changed during v2 Run snapshot creation")
    bindings = BoundPaths(root=project_root(), run_dir=run_dir)
    experiment, orbit = _compute(portable_config, cases, dataset)
    study = _study(portable_config, experiment, orbit, dataset_ref=bindings.ref(dataset), seed=seed)
    status = RunStatus.COMPLETED if experiment.gate.passed and all(orbit["checks"].values()) else RunStatus.UNVERIFIED
    log = EventLog(run_dir / "events.jsonl")
    for event_type, body in zip(EVENT_TYPES, _event_payloads(run_id, input_hash, experiment, orbit, status), strict=True):
        log.append(event_type, body)
    events = log.verify()
    run = _run_record(portable_config, cases, experiment, orbit, input_hash=input_hash,
                      seed=seed, run_dir=run_dir, events=events)
    output = {
        "experiment": experiment.model_dump(mode="json"),
        "study": study, "numerical": orbit, "run_hash": canonical_hash(run),
    }
    manifest = ReplayManifest.create(
        input_payload=input_payload, code_revision=config.source_revision,
        environment=run.environment, seed=seed,
        source_paths=[*_source_paths(), dataset],
        evidence_paths=[dataset, source_path("src/auditable_scientist/benchmark/hohmann.py"),
                        source_path("src/auditable_scientist/tools/orbit_audit_v2.py")],
        candidate_order=experiment.candidate_order, computational_output=output,
        bindings=bindings,
    )
    _write_json(run_dir / "input.json", input_payload)
    _write_json(run_dir / "run.json", run.model_dump(mode="json"))
    _write_json(run_dir / "experiment.json", output["experiment"])
    _write_json(run_dir / "study.json", study)
    _write_json(run_dir / "numerical.json", orbit)
    manifest.write(run_dir / "replay-manifest.json")
    (run_dir / "report.md").write_text(_report(run, experiment, orbit), encoding="utf-8", newline="\n")
    return run_dir


def replay_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    input_payload = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    if input_payload.get("schema_version") != "t1-cli-run-input-v2":
        raise ReplayMismatch("unsupported T1 v2 input schema")
    input_hash = canonical_hash(input_payload)
    if run_dir.name != f"run-t1-v2-{input_hash[:16]}":
        raise ReplayMismatch("T1 v2 Run directory differs from its input hash")
    config = HohmannConfig.model_validate(input_payload["config"])
    cases = [HohmannCase.model_validate(item) for item in input_payload["cases"]]
    bindings = BoundPaths(root=project_root(), run_dir=run_dir)
    dataset = bindings.resolve(config.dataset_path)
    if config.dataset_path != "run://dataset.json":
        raise ReplayMismatch("T1 v2 Run has a nonportable dataset reference")
    if canonical_hash([case.model_dump(mode="json") for case in load_hohmann_dataset(dataset)]) != canonical_hash(input_payload["cases"]):
        raise ReplayMismatch("T1 v2 dataset snapshot differs from saved input")
    experiment, orbit = _compute(config, cases, dataset)
    study = _study(config, experiment, orbit, dataset_ref=bindings.ref(dataset), seed=input_payload["seed"])
    for filename, expected in (
        ("experiment.json", experiment.model_dump(mode="json")),
        ("study.json", study), ("numerical.json", orbit),
    ):
        if json.loads((run_dir / filename).read_text(encoding="utf-8")) != expected:
            raise ReplayMismatch(f"saved T1 v2 result changed: {filename}")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl",
                            root=project_root(), bindings=bindings)
    status = RunStatus.COMPLETED if experiment.gate.passed and all(orbit["checks"].values()) else RunStatus.UNVERIFIED
    expected_run = _run_record(config, cases, experiment, orbit, input_hash=input_hash,
                               seed=input_payload["seed"], run_dir=run_dir,
                               events=run.events).model_copy(update={"created_at": run.created_at})
    if (run.run_id != run_dir.name or canonical_hash(run) != canonical_hash(expected_run)
            or [event.event_type for event in run.events] != list(EVENT_TYPES)
            or [event.payload for event in run.events]
            != _event_payloads(run.run_id, input_hash, experiment, orbit, status)):
        raise ReplayMismatch("T1 v2 shared Run, claims, policy, or event semantics differ")
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    expected_sources = [*_source_paths(), dataset]
    expected_evidence = [dataset, source_path("src/auditable_scientist/benchmark/hohmann.py"),
                         source_path("src/auditable_scientist/tools/orbit_audit_v2.py")]
    if (manifest.schema_version != "replay-manifest-v2"
            or [item.path for item in manifest.source_files] != [bindings.ref(path) for path in expected_sources]
            or [item.path for item in manifest.evidence_files] != [bindings.ref(path) for path in expected_evidence]):
        raise ReplayMismatch("T1 v2 source or evidence inventory differs")
    receipt = manifest.verify(
        input_payload=input_payload, code_revision=config.source_revision,
        environment=_environment(), seed=input_payload["seed"],
        source_paths=expected_sources, evidence_paths=expected_evidence,
        candidate_order=experiment.candidate_order,
        computational_output={"experiment": experiment.model_dump(mode="json"),
                              "study": study, "numerical": orbit, "run_hash": canonical_hash(run)},
        bindings=bindings,
    ).model_dump(mode="json")
    if (run_dir / "report.md").read_text(encoding="utf-8") != _report(run, experiment, orbit):
        raise ReplayMismatch("T1 v2 report changed")
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m auditable_scientist")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="create one offline T1 Run with analytic and RK4 tools")
    run.add_argument("config", type=Path)
    run.add_argument("--offline", action="store_true")
    run.add_argument("--seed", type=int, default=17)
    run.add_argument("--output-dir", type=Path, default=Path("artifacts/runs-v2"))
    for name in ("replay", "inspect", "export-report"):
        item = commands.add_parser(name)
        item.add_argument("run_dir", type=Path)
        if name == "export-report":
            item.add_argument("--output", type=Path)
    return parser


def _is_v2_run(run_dir: Path) -> bool:
    """Use identity markers so deleting a result cannot route around replay."""
    if run_dir.name.startswith("run-t1-v2-"):
        return True
    for filename, key, expected in (
        ("input.json", "schema_version", "t1-cli-run-input-v2"),
        ("run.json", "run_id", "run-t1-v2-"),
    ):
        path = run_dir / filename
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8")).get(key, "")
        except (json.JSONDecodeError, AttributeError):
            continue
        if value == expected or (key == "run_id" and isinstance(value, str) and value.startswith(expected)):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] in ("init", "init-track", "run-track"):
        return legacy_cli.main(arguments)
    args = build_parser().parse_args(arguments)
    try:
        if args.command == "run":
            print(build_run(args.config, seed=args.seed, output_dir=args.output_dir))
        elif args.command == "replay":
            if not _is_v2_run(args.run_dir):
                return legacy_cli.main(arguments)
            print(json.dumps(replay_run(args.run_dir), indent=2, sort_keys=True))
        elif args.command == "inspect":
            if not _is_v2_run(args.run_dir):
                return legacy_cli.main(arguments)
            replay_run(args.run_dir)
            run = json.loads((args.run_dir / "run.json").read_text(encoding="utf-8"))
            experiment = json.loads((args.run_dir / "experiment.json").read_text(encoding="utf-8"))
            orbit = json.loads((args.run_dir / "numerical.json").read_text(encoding="utf-8"))
            print(json.dumps({"run_id": run["run_id"], "status": run["status"],
                              "selected_candidate_id": experiment["selected_candidate_id"],
                              "holdout": experiment["gate"], "numerical": orbit["summary"],
                              "claims": run["claims"]}, indent=2, sort_keys=True))
        elif args.command == "export-report":
            if _is_v2_run(args.run_dir):
                replay_run(args.run_dir)
            source = args.run_dir / "report.md"
            destination = args.output or source
            if destination.resolve() != source.resolve():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            print(destination)
        return 0
    except (FileNotFoundError, ValueError, OSError, PermissionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
