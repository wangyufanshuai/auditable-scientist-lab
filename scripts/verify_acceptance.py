"""Fail-closed verifier for the local T1–T5 acceptance receipts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator

from auditable_scientist.cli_v3 import historical_source_matches, replay_verified_run
from auditable_scientist.benchmark.hohmann import GRAMMAR_VERSION
from auditable_scientist.domain import Run
from auditable_scientist.adapters import Project05Adapter, Project05Snapshot, built_in_manifests
from auditable_scientist.runtime.event_log import EventLog
from auditable_scientist.runtime.canonical import canonical_hash
from auditable_scientist.runtime.replay import BoundPaths, ReplayManifest, ReplayReceipt, fingerprint_file
from auditable_scientist.runtime.run_integrity import verify_run_record
from auditable_scientist.tracks.causal import CausalCase, evaluate_causal_fixture
from auditable_scientist.tracks.common import TrackReceipt
from auditable_scientist.tracks.dynamics import DynamicsCase, evaluate_dynamics_fixture
from auditable_scientist.tracks.nbody import NBodyCase, evaluate_nbody_fixture
from auditable_scientist.tracks.oscillator_proof import OscillatorProofPackage, verify_oscillator_package
from auditable_scientist.tracks.physical_world import PhysicalCase, compare, evaluate_physical_fixture, standard_cases
from auditable_scientist.tracks.proof import ProofPackage, verify_proof_package
from auditable_scientist.tracks.protocol import ProtocolSpec, ProtocolStep, verify_protocol
from auditable_scientist.tracks.runner import run_registered_track
from auditable_scientist.tools.numerical import hohmann_baseline
if __package__:
    from .verify_t1_core_orbit import build_audit as build_t1_core_orbit_audit
else:
    from verify_t1_core_orbit import build_audit as build_t1_core_orbit_audit


ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def wheel_source_snapshot_hash(root: Path = ROOT) -> str:
    digest = hashlib.sha256()
    paths = [root / "pyproject.toml", *sorted(
        path for path in (root / "src/auditable_scientist").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )]
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def verify_core_t1_orbit() -> dict:
    """Recompute the dependency-free propagation receipt in the core environment."""
    saved = load("artifacts/t1-core-orbit-audit.json")
    recorded_at = saved.pop("recorded_at", None)
    if not isinstance(recorded_at, str):
        raise ValueError("T1 core orbit audit has no timestamp")
    timestamp = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("T1 core orbit audit timestamp is naive")
    expected = build_t1_core_orbit_audit()
    if (saved != expected or expected["status"] != "verified-synthetic-two-body-only"
            or not all(expected["checks"].values())
            or expected["boundaries"]["core_cli_run_integrated"] is not False):
        raise ValueError("T1 core orbit recomputation, source, or scope differs")
    return {"scope": "dynamic-pure-python-synthetic-two-body-recomputation",
            "source_files_match": True, "checks": expected["checks"]}


def verify_core_t1_orbit_run() -> dict:
    """Recompute the versioned numerical Tool/Provider Run and its mutations."""
    audit = load("artifacts/t1-core-orbit-run-audit.json")
    relative = Path(audit.get("run_path", ""))
    boundaries = {
        "synthetic_two_body_grid": True, "shared_kernel_run": True,
        "main_cli_integrated": False, "independent_orbit_derivation": False,
        "real_data": False, "dated_ephemeris": False,
        "mission_validity": False, "publication_ready": False,
    }
    if (audit.get("schema_version") != "t1-core-orbit-run-audit-v1"
            or audit.get("status") != "verified-synthetic-two-body-run-only"
            or audit.get("provider_id") != "internal-rk4-t1-orbit-v1"
            or audit.get("provider_version") != "internal-rk4-v1"
            or audit.get("boundaries") != boundaries
            or audit.get("relocated_replay_equal") is not True
            or audit.get("result_tamper_rejected") is not True
            or audit.get("snapshot_tamper_rejected") is not True
            or audit.get("policy_denials") != {
                "wrong_provider_rejected": True, "out_of_scope_path_rejected": True,
            }
            or relative.parts[:2] != ("artifacts", "t1-core-orbit-runs")
            or len(relative.parts) != 3 or relative.name != audit.get("run_id")
            or not relative.name.startswith("run-t1-core-orbit-")
            or audit.get("replay", {}).get("verified") is not True
            or len(audit["replay"].get("checks", [])) != 8):
        raise ValueError("versioned T1 core orbit Run is missing or exceeds its boundary")
    run = load((relative / "run.json").as_posix())
    if (run.get("claims", [{}])[0].get("status") != "unverified"
            or run["claims"][0].get("level") != "demo"
            or run.get("environment", {}).get("network") != "disabled"
            or run.get("status") != "completed"):
        raise ValueError("T1 numerical Run claim, network, or lifecycle was promoted")
    replay = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_t1_core_orbit_run.py"), "--verify"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if replay.returncode != 0:
        raise ValueError(f"T1 numerical Run dynamic replay failed: {replay.stderr.strip()}")
    observed = json.loads(replay.stdout)
    if (observed.get("status") != audit["status"] or observed.get("run_id") != audit["run_id"]
            or observed.get("replay") != audit["replay"]
            or observed.get("mutation_controls") != [True, True]):
        raise ValueError("T1 numerical Run dynamic replay differs from saved receipt")
    return {"run_id": audit["run_id"], "replay": audit["replay"],
            "mutation_controls": observed["mutation_controls"], "main_cli_integrated": False}


def verify_combined_t1_cli() -> dict:
    """Recompute the v2 package CLI Run without weakening historical replay."""
    audit = load("artifacts/t1-combined-cli-audit-v4.json")
    relative = Path(audit.get("run_path", ""))
    expected_checks = {
        "one_combined_run", "fixed_holdout_passed", "numerical_grid_passed",
        "mission_claim_unverified", "network_disabled", "cli_replay_equal",
        "cli_inspect_bound", "report_export_equal", "relocated_replay_equal",
        "legacy_t1_replay_preserved", "numerical_tamper_rejected",
        "dataset_tamper_rejected", "event_tamper_rejected", "claim_tamper_rejected",
        "missing_numerical_tamper_rejected",
    }
    expected_boundaries = {
        "package_module_cli_integrated": True, "console_script_versioned_router": True,
        "independent_time_propagation": True, "independent_orbit_derivation": False,
        "synthetic_fixture_only": True, "real_data": False,
        "dated_ephemeris": False, "mission_trajectory_validated": False,
        "publication_ready": False,
    }
    sources = audit.get("source_files", [])
    if (audit.get("schema_version") != "t1-combined-cli-audit-v4"
            or audit.get("status") != "verified-bounded-combined-cli-run"
            or audit.get("boundaries") != expected_boundaries
            or set(audit.get("checks", {})) != expected_checks
            or not all(audit["checks"].values())
            or audit.get("replay", {}).get("verified") is not True
            or len(audit["replay"].get("checks", [])) != 8
            or audit.get("legacy_replay", {}).get("verified") is not True
            or relative.parts[:2] != ("artifacts", "t1-combined-runs-v3")
            or len(relative.parts) != 3 or relative.name != audit.get("run_id")
            or not relative.name.startswith("run-t1-v2-")
            or {item.get("path") for item in sources} != {
                "scripts/verify_t1_combined_cli.py", "docs/T1_COMBINED_CLI_V2.md",
                "src/auditable_scientist/__main__.py", "src/auditable_scientist/cli_v2.py",
                "src/auditable_scientist/cli_v3.py",
                "src/auditable_scientist/_resources/legacy-runtime-8c26a26.zip",
                "src/auditable_scientist/tools/orbit_audit_v2.py", "pyproject.toml",
            } or len(sources) != 8):
        raise ValueError("T1 combined CLI audit identity, checks, or boundary differs")
    for item in sources:
        path = ROOT / item["path"]
        if (fingerprint_file(path).sha256 != item.get("sha256")
                or path.stat().st_size != item.get("bytes")):
            raise ValueError(f"T1 combined CLI source changed: {item['path']}")
    run = load((relative / "run.json").as_posix())
    if ([item.get("status") for item in run.get("claims", [])] != ["reproduced", "unverified"]
            or [item.get("level") for item in run["claims"]] != ["validated-reproduction", "demo"]
            or len(run.get("tools", [])) != 2 or run.get("policy", {}).get("network") != "disabled"):
        raise ValueError("T1 v2 CLI Run exceeded its synthetic and mission claim boundary")
    command = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_t1_combined_cli.py"), "--verify"],
        cwd=ROOT, capture_output=True, text=True, check=False, timeout=120,
    )
    if command.returncode != 0:
        raise ValueError(f"T1 v2 CLI dynamic audit failed: {command.stderr.strip()}")
    observed = json.loads(command.stdout)
    if (observed.get("status") != audit["status"] or observed.get("run_id") != audit["run_id"]
            or observed.get("replay") != audit["replay"] or observed.get("checks") != audit["checks"]):
        raise ValueError("T1 v2 CLI dynamic audit differs from saved receipt")
    return {"run_id": audit["run_id"], "replay": audit["replay"],
            "checks": audit["checks"], "console_script_versioned_router": True}


def verify_optional_t1_de440s() -> dict:
    """Check the saved source contract; rerun only when the optional kernel is present."""

    audit = load("artifacts/t1-de440s-ephemeris-audit.json")
    snapshot = load("artifacts/t1-de440s-ephemeris-snapshot.json")
    expected_sources = {
        "scripts/verify_t1_de440s_ephemeris.py", "scripts/fetch_de440s.py",
        "src/auditable_scientist/adapters/naif_de440s.py",
        "docs/T1_DE440S_EPHEMERIS.md", "requirements-t1-de440s-win-py312.txt",
    }
    sources = audit.get("source_files", [])
    boundaries = audit.get("boundaries", {})
    rights = audit.get("source_rights", {})
    snapshot_bytes = (json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                                 allow_nan=False) + "\n").encode("utf-8")
    if (audit.get("schema_version") != "t1-de440s-ephemeris-audit-v1"
            or audit.get("status") != "verified-source-tracked-geometry-only"
            or set(audit.get("checks", {})) != {
                "official_md5_matched", "pinned_sha256_matched", "fixed_departure_dates",
                "finite_dated_geometry", "reader_and_frame_explicit",
                "mission_claim_unverified", "wrong_kernel_rejected",
            }
            or not all(audit["checks"].values())
            or {item.get("path") for item in sources} != expected_sources
            or len(sources) != len(expected_sources)
            or any(fingerprint_file(ROOT / item["path"]).sha256 != item.get("sha256")
                   or (ROOT / item["path"]).stat().st_size != item.get("bytes")
                   for item in sources)
            or audit.get("snapshot_sha256") != hashlib.sha256(snapshot_bytes).hexdigest()
            or audit.get("kernel_source") != snapshot.get("source")
            or audit.get("kernel_local_path") != "data/naif/de440s.bsp"
            or snapshot.get("source", {}).get("sha256") != "c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2"
            or snapshot.get("source", {}).get("md5") != "3917ee56769db332790c751e2168843d"
            or snapshot.get("claim_status") != "unverified"
            or snapshot.get("evidence_level") != "real-data"
            or [row.get("departure_jd_tdb") for row in snapshot.get("cases", [])] != [2460584.5, 2461375.5]
            or snapshot.get("coordinate_contract", {}).get("mars_target") != "MARS BARYCENTER (4), not Mars center (499)"
            or rights.get("rules_url") != "https://naif.jpl.nasa.gov/naif/rules.html"
            or rights.get("kernel_redistributed_in_repository") is not False
            or rights.get("applies_to_unrelated_sources") is not False
            or boundaries != {
                "external_ephemeris_model_used": True,
                "real_ephemeris_source_tracked": True,
                "mars_center_state_available": False,
                "spacecraft_trajectory_propagated": False,
                "mission_trajectory_validated": False,
                "scientific_holdout": False,
                "publication_ready": False,
            }):
        raise ValueError("DE440s saved source, rights, or scientific boundary differs")
    recorded_at = audit.get("recorded_at")
    if not isinstance(recorded_at, str) or datetime.fromisoformat(recorded_at).tzinfo is None:
        raise ValueError("DE440s audit has no timezone-aware timestamp")
    kernel = ROOT / "data/naif/de440s.bsp"
    dynamic_verified = False
    if kernel.is_file() and importlib.util.find_spec("spiceypy") is not None:
        command = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_t1_de440s_ephemeris.py"), "--verify"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=120,
        )
        if command.returncode != 0 or json.loads(command.stdout).get("status") != audit["status"]:
            raise ValueError(f"DE440s optional dynamic audit failed: {command.stderr.strip()}")
        dynamic_verified = True
    return {"status": audit["status"], "snapshot_sha256": audit["snapshot_sha256"],
            "dynamic_verified_here": dynamic_verified,
            "mission_trajectory_validated": False}


def verify_optional_t1_de440s_run() -> dict:
    """Replay the copied ephemeris snapshot without requiring the NAIF kernel."""

    audit = load("artifacts/t1-de440s-run-audit.json")
    expected_boundaries = {
        "real_ephemeris_source_tracked": True,
        "dynamic_kernel_recomputed_in_replay": False,
        "mars_center_encounter_validated": False,
        "spacecraft_trajectory_validated": False,
        "scientific_holdout": False,
        "mission_claim_verified": False,
        "publication_ready": False,
    }
    relative = Path(audit.get("run_path", ""))
    if (audit.get("schema_version") != "t1-de440s-run-audit-v1"
            or audit.get("status") != "verified-offline-snapshot-geometry-run-only"
            or relative.is_absolute() or ".." in relative.parts
            or relative.parts[:1] != ("artifacts",)
            or audit.get("run_id") != relative.name
            or audit.get("boundaries") != expected_boundaries
            or audit.get("relocated_replay_equal") is not True
            or audit.get("result_tamper_rejected") is not True
            or audit.get("snapshot_tamper_rejected") is not True
            or audit.get("policy_denials") != {
                "wrong_provider_rejected": True,
                "out_of_scope_path_rejected": True,
            }
            or audit.get("replay", {}).get("verified") is not True):
        raise ValueError("DE440s portable Run identity or boundary differs")
    recorded_at = audit.get("recorded_at")
    if not isinstance(recorded_at, str) or datetime.fromisoformat(recorded_at).tzinfo is None:
        raise ValueError("DE440s portable Run has no timezone-aware timestamp")
    command = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_t1_de440s_run.py"), "--verify"],
        cwd=ROOT, capture_output=True, text=True, check=False, timeout=120,
    )
    if command.returncode != 0:
        raise ValueError(f"DE440s portable Run replay failed: {command.stderr.strip()}")
    observed = json.loads(command.stdout)
    if (observed.get("status") != audit["status"]
            or observed.get("run_id") != audit["run_id"]
            or observed.get("replay") != audit["replay"]
            or observed.get("mutation_controls") != [True, True]):
        raise ValueError("DE440s portable Run differs from saved receipt")
    return {"run_id": audit["run_id"], "replay": audit["replay"],
            "snapshot_geometry_only": True, "mission_claim_verified": False}


def verify_optional_t1_mars_center() -> dict:
    """Bind the MAR099s correction without treating it as mission validation."""

    audit = load("artifacts/t1-mars-center-ephemeris-audit.json")
    snapshot = load("artifacts/t1-mars-center-ephemeris-snapshot.json")
    expected_sources = {
        "scripts/verify_t1_mars_center_ephemeris.py", "scripts/fetch_mar099s.py",
        "src/auditable_scientist/adapters/naif_mars_center.py",
        "src/auditable_scientist/adapters/naif_de440s.py",
        "docs/T1_MARS_CENTER_EPHEMERIS.md", "requirements-t1-mars-center-win-py312.txt",
        "artifacts/t1-de440s-ephemeris-snapshot.json",
    }
    expected_checks = {
        "official_md5_matched", "pinned_sha256_matched", "de440s_source_preserved",
        "fixed_departure_dates", "planetary_states_preserved", "mars_499_coverage",
        "center_offset_bounded", "spice_chain_consistent", "mission_claim_unverified",
        "wrong_kernel_rejected",
    }
    expected_boundaries = {
        "mars_center_state_available": True,
        "source_tracked_ephemeris_geometry": True,
        "independent_planetary_ephemeris": False,
        "spacecraft_trajectory_propagated": False,
        "mission_trajectory_validated": False,
        "scientific_holdout": False,
        "publication_ready": False,
    }
    sources = audit.get("source_files", [])
    snapshot_bytes = (json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                                 allow_nan=False) + "\n").encode("utf-8")
    if (audit.get("schema_version") != "t1-mars-center-ephemeris-audit-v1"
            or audit.get("status") != "verified-source-tracked-center-geometry-only"
            or set(audit.get("checks", {})) != expected_checks
            or not all(audit["checks"].values())
            or audit.get("boundaries") != expected_boundaries
            or {item.get("path") for item in sources} != expected_sources
            or len(sources) != len(expected_sources)
            or any(fingerprint_file(ROOT / item["path"]).sha256 != item.get("sha256")
                   or (ROOT / item["path"]).stat().st_size != item.get("bytes")
                   for item in sources)
            or audit.get("snapshot_sha256") != hashlib.sha256(snapshot_bytes).hexdigest()
            or audit.get("kernel_local_paths") != {
                "de440s": "data/naif/de440s.bsp", "mar099s": "data/naif/mar099s.bsp"}
            or snapshot.get("sources") != audit.get("kernel_sources")
            or snapshot.get("sources", {}).get("mar099s", {}).get("md5") !=
            "fd7302dfbaa0c63ce85b1e98923ee6a1"
            or snapshot.get("sources", {}).get("mar099s", {}).get("sha256") !=
            "997dc93ba640e476da7a494d2237dcdeb145e528db37be8ccee588c615e4e1ff"
            or snapshot.get("claim_status") != "unverified"
            or snapshot.get("evidence_level") != "real-data"
            or snapshot.get("mars_499_coverage_et_seconds") != [-157809600.0, 1577880000.0]
            or [row.get("departure_jd_tdb") for row in snapshot.get("cases", [])] !=
            [2460584.5, 2461375.5]
            or any(not 0 <= row["center_barycenter_separation_m"] < 1
                   or not 0 <= row["mars_center_arrival_gap_km"] < 600_000_000
                   for row in snapshot["cases"])
            or audit.get("source_rights", {}).get("kernels_redistributed_in_repository") is not False
            or audit.get("source_rights", {}).get("applies_to_unrelated_sources") is not False):
        raise ValueError("Mars-center saved source, rights, or scientific boundary differs")
    recorded_at = audit.get("recorded_at")
    if not isinstance(recorded_at, str) or datetime.fromisoformat(recorded_at).tzinfo is None:
        raise ValueError("Mars-center audit has no timezone-aware timestamp")
    de440s = ROOT / "data/naif/de440s.bsp"
    mar099s = ROOT / "data/naif/mar099s.bsp"
    dynamic_verified = False
    if (de440s.is_file() and mar099s.is_file()
            and importlib.util.find_spec("spiceypy") is not None):
        command = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_t1_mars_center_ephemeris.py"), "--verify"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=120,
        )
        if command.returncode != 0 or json.loads(command.stdout).get("status") != audit["status"]:
            raise ValueError(f"Mars-center dynamic audit failed: {command.stderr.strip()}")
        dynamic_verified = True
    return {"status": audit["status"], "snapshot_sha256": audit["snapshot_sha256"],
            "dynamic_verified_here": dynamic_verified, "mars_center_state_available": True,
            "mission_trajectory_validated": False}


def verify_optional_t1_maven_source() -> dict:
    """Check a NAV spacecraft-state source without promoting mission validation."""

    audit = load("artifacts/t1-maven-source-audit.json")
    snapshot = load("artifacts/t1-maven-source-snapshot.json")
    expected_sources = {
        "scripts/fetch_maven_cruise.py", "scripts/verify_t1_maven_source.py",
        "src/auditable_scientist/adapters/naif_de440s.py",
        "src/auditable_scientist/adapters/naif_mars_center.py",
        "docs/T1_MAVEN_MISSION_SOURCE.md", "requirements-t1-mars-center-win-py312.txt",
    }
    expected_checks = {
        "pds_label_md5_and_size_matched", "pinned_sha256_matched", "three_declared_samples",
        "center_transition_observed", "mars_approach_observed", "direct_chain_consistent",
        "mission_claim_unverified", "wrong_kernel_rejected",
    }
    expected_boundaries = {
        "archived_spacecraft_states_available": True,
        "independent_planetary_ephemeris": False,
        "independent_spacecraft_propagation": False,
        "mission_validation": False,
        "scientific_holdout": False,
        "publication_ready": False,
    }
    sources = audit.get("source_files", [])
    snapshot_bytes = (json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                                 allow_nan=False) + "\n").encode("utf-8")
    samples = snapshot.get("samples", [])
    if (audit.get("schema_version") != "t1-maven-source-audit-v1"
            or audit.get("status") != "verified-source-tracked-reconstructed-mission-geometry-only"
            or set(audit.get("checks", {})) != expected_checks
            or not all(audit["checks"].values())
            or audit.get("boundaries") != expected_boundaries
            or len(sources) != len(expected_sources)
            or {item.get("path") for item in sources} != expected_sources
            or any(fingerprint_file(ROOT / item["path"]).sha256 != item.get("sha256")
                   or (ROOT / item["path"]).stat().st_size != item.get("bytes")
                   for item in sources)
            or audit.get("snapshot_sha256") != hashlib.sha256(snapshot_bytes).hexdigest()
            or audit.get("kernel_local_paths") != {
                "de440s": "data/naif/de440s.bsp", "mar099s": "data/naif/mar099s.bsp",
                "maven_cruise": "data/naif/maven_cru_rec_131118_140923_v1.bsp"}
            or snapshot.get("schema_version") != "t1-maven-source-snapshot-v1"
            or snapshot.get("spacecraft_id") != -202
            or snapshot.get("mission_product", {}).get("md5") != "8d7c55ef3bb935ad487c529f5be5343d"
            or snapshot.get("mission_product", {}).get("sha256") !=
            "07c76dfc2a1f66a54b4dd74105b2a5a70d72192813abee3659a74d4d21988dc5"
            or snapshot.get("mission_product", {}).get("bytes") != 4_797_440
            or snapshot.get("claim_status") != "unverified"
            or snapshot.get("sampling_status") != "exploratory-selected-after-source-inspection; not a holdout"
            or snapshot.get("coordinate_contract", {}).get("kernel_load_order") !=
            ["maven_cruise", "mar099s", "de440s"]
            or [row.get("et_tdb_seconds_past_j2000") for row in samples] !=
            [446_904_000.0, 464_616_000.0, 464_702_400.0]
            or [row.get("maven_segment_center_id") for row in samples] != [10, 4, 4]
            or any(row.get("chain_position_error_m", float("inf")) >= 0.001 for row in samples)
            or audit.get("source_rights", {}).get("unmodified_kernel_redistributed") is not False):
        raise ValueError("MAVEN saved source, rights, or scientific boundary differs")
    recorded_at = audit.get("recorded_at")
    if not isinstance(recorded_at, str) or datetime.fromisoformat(recorded_at).tzinfo is None:
        raise ValueError("MAVEN source audit has no timezone-aware timestamp")
    dynamic_verified = False
    if (all((ROOT / path).is_file() for path in audit["kernel_local_paths"].values())
            and importlib.util.find_spec("spiceypy") is not None):
        command = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_t1_maven_source.py"), "--verify"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=120,
        )
        if command.returncode != 0 or json.loads(command.stdout).get("status") != audit["status"]:
            raise ValueError(f"MAVEN dynamic source audit failed: {command.stderr.strip()}")
        dynamic_verified = True
    return {"status": audit["status"], "snapshot_sha256": audit["snapshot_sha256"],
            "dynamic_verified_here": dynamic_verified, "archived_spacecraft_states_available": True,
            "independent_spacecraft_propagation": False, "mission_validation": False}


def verify_optional_t1_orbit_static() -> dict:
    """Check saved external-solver provenance and bounds without importing SciPy."""
    audit = load("artifacts/t1-external-orbit-audit.json")
    expected_sources = {
        "scripts/verify_t1_external_orbit.py",
        "scripts/verify_t1_nasa_factsheets.py",
        "scripts/verify_t3_external_scipy.py",
        "src/auditable_scientist/tools/numerical.py",
        "examples/hohmann/dataset.json",
        "artifacts/t1-nasa-factsheet-snapshot.json",
        "artifacts/t1-nasa-factsheet-audit.json",
        "requirements-t3-scipy-win-py312.txt",
    }
    sources = audit.get("source_files", [])
    boundaries = audit.get("boundaries", {})
    environment = audit.get("environment", {})
    if (
        audit.get("schema_version") != "t1-external-orbit-audit-v1"
        or audit.get("status") != "passed-within-circular-two-body-scope"
        or audit.get("scope") != "Event-driven, dimensionless, heliocentric two-body apoapsis integration for nine synthetic T1 cases and one NASA-rounded-axis sensitivity case"
        or audit.get("solver") != {"api": "scipy.integrate.solve_ivp", "method": "DOP853", "rtol": 3e-12, "atol": 3e-14}
        or environment.get("platform_and_packages") != {
            "python": "3.12.3", "implementation": "CPython", "system": "Windows", "machine": "AMD64",
            "numpy": "2.2.6", "scipy": "1.18.1",
        }
        or environment.get("lock_sha256") != fingerprint_file(ROOT / "requirements-t3-scipy-win-py312.txt").sha256
        or environment != load("artifacts/t3-external-scipy.json").get("environment")
        or len(sources) != len(expected_sources)
        or {item.get("path") for item in sources} != expected_sources
        or boundaries != {
            "core_dependency": False,
            "circular_two_body_numerical_cross_check": True,
            "real_data": False,
            "dated_ephemeris": False,
            "mission_trajectory_validated": False,
            "publication_ready": False,
            "nasa_source_rights_status": "unreviewed-page-specific",
        }
    ):
        raise ValueError("T1 external orbit audit identity, environment, or boundary differs")
    recorded_at = datetime.fromisoformat(audit["recorded_at"].replace("Z", "+00:00"))
    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
        raise ValueError("T1 external orbit audit timestamp is naive")
    for item in sources:
        fingerprint = fingerprint_file(ROOT / item["path"])
        if fingerprint.sha256 != item.get("sha256") or fingerprint.bytes != item.get("bytes"):
            raise ValueError(f"T1 external orbit source changed: {item['path']}")
    fixture = load("examples/hohmann/dataset.json")
    nasa = load("artifacts/t1-nasa-factsheet-audit.json")
    expected_inputs = [
        (item["case_id"], item["split"], item["r1_km"], item["r2_km"], item["mu_km3_s2"])
        for item in fixture["cases"]
    ]
    expected_inputs.append((
        "nasa-rounded-axes", "external-parameter-sensitivity",
        float(nasa["rounded_axes_million_km"]["earth"]) * 1_000_000,
        float(nasa["rounded_axes_million_km"]["mars"]) * 1_000_000,
        fixture["cases"][0]["mu_km3_s2"],
    ))
    rows = audit.get("rows", [])
    actual_inputs = [
        (row["case_id"], row["split"], row["r1_km"], row["r2_km"], row["mu_km3_s2"])
        for row in rows
    ]
    if actual_inputs != expected_inputs or len(rows) != 10 or not all(row.get("event_detected") is True for row in rows):
        raise ValueError("T1 external orbit audit inputs or apoapsis results differ")
    for row in rows:
        reference = hohmann_baseline(row["r1_km"], row["r2_km"], row["mu_km3_s2"])
        numerical_days = row["numerical_tof_days"]
        observed_relative = abs(numerical_days - reference.time_of_flight_days) / reference.time_of_flight_days
        if (not isinstance(row.get("function_calls"), int) or row["function_calls"] <= 0
                or not math.isfinite(numerical_days) or numerical_days <= 0
                or not math.isclose(row["analytic_tof_days"], reference.time_of_flight_days, rel_tol=0, abs_tol=1e-12)
                or not math.isclose(row["relative_tof_error"], observed_relative, rel_tol=0, abs_tol=2e-15)):
            raise ValueError(f"T1 external orbit time arithmetic differs: {row['case_id']}")
    gates = audit.get("gates", {})
    metrics = (
        "relative_tof_error", "relative_final_position_error", "relative_final_velocity_error",
        "relative_energy_drift", "relative_angular_momentum_drift",
    )
    if gates.get("case_count") != 10 or any(gates.get(f"{metric}_max") != 1e-9 for metric in metrics):
        raise ValueError("T1 external orbit gates differ")
    for metric in metrics:
        values = [row[metric] for row in rows]
        if (not all(math.isfinite(value) and value >= 0 for value in values)
                or audit["summary"][metric] != max(values)
                or max(values) > gates[f"{metric}_max"]):
            raise ValueError(f"T1 external orbit metric differs or fails: {metric}")
    if (audit.get("checks") != {
        "ten_apoapses_detected": True, "time_agreement": True, "position_agreement": True,
        "velocity_agreement": True, "energy_conservation": True,
        "angular_momentum_conservation": True, "repulsive_gravity_rejected": True,
    } or audit.get("negative_control", {}).get("gravity_sign") != -1
            or audit["negative_control"].get("event_detected") is not False):
        raise ValueError("T1 external orbit checks or wrong-gravity control differ")
    return {"scope": "static-source-and-boundary-check-only", "source_files_match": True,
            "dynamic_recalculation_required": "python scripts/verify_t1_external_orbit.py --verify"}


def verify_optional_t1_run_static() -> dict:
    """Verify the saved T1 Tool/Provider Run without importing its SciPy backend."""
    audit = load("artifacts/t1-external-run-audit.json")
    relative = audit.get("run_path", "")
    if (
        audit.get("schema_version") != "t1-external-run-audit-v1"
        or audit.get("status") != "verified-within-pinned-two-body-grid"
        or not isinstance(relative, str)
        or not relative.startswith("artifacts/t1-external-runs/run-t1-scipy-orbit-")
        or Path(relative).is_absolute() or ".." in Path(relative).parts
        or audit.get("relocated_replay_equal") is not True
        or audit.get("result_tamper_rejected") is not True
        or audit.get("license_tamper_rejected") is not True
        or audit.get("policy_denials") != {"wrong_provider_rejected": True, "out_of_scope_path_rejected": True}
        or audit.get("provider_id") != "scipy-dop853-t1-orbit-v1"
        or audit.get("provider_version") != "scipy-1.18.1-numpy-2.2.6"
        or audit.get("boundaries") != {
            "synthetic_two_body_grid": True, "core_t1_run": False,
            "real_data": False, "dated_ephemeris": False, "mission_validity": False,
            "publication_ready": False, "nasa_rights_status": "unreviewed-page-specific",
        }
    ):
        raise ValueError("optional T1 external Run is missing or exceeds its boundary")
    recorded_at = datetime.fromisoformat(audit["recorded_at"].replace("Z", "+00:00"))
    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
        raise ValueError("optional T1 external Run audit timestamp is naive")
    run_dir = (ROOT / relative).resolve()
    if not run_dir.is_relative_to((ROOT / "artifacts/t1-external-runs").resolve()):
        raise ValueError("optional T1 external Run escaped its artifact directory")
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    saved_input = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    saved_result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    receipt = saved_result.get("receipt")
    static_receipt = load("artifacts/t1-external-orbit-audit.json")
    static_receipt.pop("recorded_at", None)
    provider_environment = static_receipt.get("environment", {})
    fixture = load("examples/hohmann/dataset.json")
    if (
        saved_input.get("schema_version") != "t1-scipy-orbit-run-input-v1"
        or saved_input.get("track_id") != "T1"
        or saved_input.get("provider_id") != "scipy-dop853-t1-orbit-v1"
        or saved_input.get("case_ids") != [item["case_id"] for item in fixture["cases"]] + ["nasa-rounded-axes"]
        or saved_result.get("provider_id") != "scipy-dop853-t1-orbit-v1"
        or run_dir.name != f"run-t1-scipy-orbit-{canonical_hash(saved_input)[:16]}"
        or audit.get("run_id") != run_dir.name
        or not isinstance(receipt, dict) or receipt != static_receipt
        or receipt.get("environment") != saved_input.get("provider_provenance")
        or receipt.get("gates") != saved_input.get("gates")
        or receipt.get("solver") != saved_input.get("solver")
        or audit.get("pinned_wheel_sha256") != provider_environment.get("wheel_sha256")
        or audit.get("license_sha256") != {
            "scipy": provider_environment.get("scipy_installed_license_sha256"),
            "numpy": provider_environment.get("numpy_installed_license_sha256"),
        }
        or audit.get("source_tag_and_commit") != {
            "scipy": [provider_environment.get("scipy_source_tag"), provider_environment.get("scipy_source_commit")],
            "numpy": [provider_environment.get("numpy_source_tag"), provider_environment.get("numpy_source_commit")],
        }
    ):
        raise ValueError("optional T1 external Run input or result differs")
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    expected_sources = {
        "root://scripts/verify_t1_external_orbit_run.py",
        "root://scripts/verify_t1_external_orbit.py",
        "root://scripts/verify_t1_nasa_factsheets.py",
        "root://scripts/verify_t3_external_scipy.py",
        "root://src/auditable_scientist/tools/numerical.py",
        "root://src/auditable_scientist/domain/models.py",
        "root://src/auditable_scientist/policy/runtime.py",
        "root://src/auditable_scientist/runtime/canonical.py",
        "root://src/auditable_scientist/runtime/environment.py",
        "root://src/auditable_scientist/runtime/event_log.py",
        "root://src/auditable_scientist/runtime/replay.py",
        "root://src/auditable_scientist/runtime/run_integrity.py",
        "root://src/auditable_scientist/runtime/paths.py",
        "root://examples/hohmann/dataset.json",
        "root://artifacts/t1-nasa-factsheet-snapshot.json",
        "root://artifacts/t1-nasa-factsheet-audit.json",
        "root://docs/T1_EXTERNAL_ORBIT.md",
        "root://docs/contracts/t1-external-tool-call-v1.json",
        "root://artifacts/t1-external-orbit-audit.json",
        "root://requirements-t3-scipy-win-py312.txt",
        "root://docs/EVIDENCE_POLICY.md",
    }
    source_refs = {item.path for item in manifest.source_files}
    evidence_refs = {item.path for item in manifest.evidence_files}
    if (
        manifest.schema_version != "replay-manifest-v2"
        or source_refs != expected_sources
        or len(manifest.source_files) != len(expected_sources)
        or any(not ref.startswith("root://") for ref in source_refs)
        or evidence_refs != {"run://scipy-license.txt", "run://numpy-license.txt"}
        or saved_input.get("source_snapshot_hash") != canonical_hash([
            (item.path.removeprefix("root://"), item.sha256) for item in manifest.source_files
        ])
    ):
        raise ValueError("optional T1 external Run source or license inventory differs")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl", root=ROOT, bindings=bindings)
    if (
        run.run_id != run_dir.name or run.input_hash != canonical_hash(saved_input)
        or run.status.value != "completed"
        or len(run.claims) != 1 or run.claims[0].status.value != "unverified"
        or run.claims[0].holdout_verified is not False
        or run.claims[0].level.value != "validated-reproduction"
        or any(item.provenance_status.value != "unverified" for item in run.evidence)
        or run.policy is None or run.policy.network != "disabled"
        or run.policy.max_tool_calls != 1 or run.policy.max_seconds != 120
        or run.policy.allowed_providers != ["scipy-dop853-t1-orbit-v1"]
        or set(run.policy.allowed_paths) != source_refs | evidence_refs
        or len(run.tools) != 1 or run.tools[0].tool_id != "t1-scipy-two-body-apoapsis-v1"
        or len(run.providers) != 1 or run.providers[0].provider_id != "scipy-dop853-t1-orbit-v1"
        or run.environment.get("pinned_wheel_sha256") != audit.get("pinned_wheel_sha256")
        or run.environment.get("installed_license_sha256") != audit.get("license_sha256")
        or run.environment.get("nasa_source_rights_status") != "unreviewed-page-specific"
    ):
        raise ValueError("optional T1 external shared Run widened its claim, policy, or provenance")
    event_types = [event.event_type for event in run.events]
    if event_types != [
        "run.initialized", "policy.applied", "tool.invoked", "evaluator.completed",
        "negative_case.checked", "run.completed",
    ]:
        raise ValueError("optional T1 external Run lifecycle differs")
    if (run.events[3].payload != {
        "evaluator_id": "t1-scipy-orbit-crosscheck-v1",
        "summary": receipt["summary"], "checks": receipt["checks"],
    } or run.events[4].payload != {
        "wrong_gravity_event_detected": False, "rejected": True,
    }):
        raise ValueError("optional T1 external Run evaluator or negative event differs")
    replay = manifest.verify(
        input_payload=saved_input, code_revision=run.code_revision, environment=run.environment,
        seed=run.seed, source_paths=[bindings.resolve(item.path) for item in manifest.source_files],
        evidence_paths=[bindings.resolve(item.path) for item in manifest.evidence_files],
        candidate_order=[], computational_output=receipt, bindings=bindings,
    ).model_dump(mode="json")
    if audit.get("replay") != replay or len(replay["checks"]) != 8:
        raise ValueError("optional T1 external Run replay binding differs")
    return replay


def verify_optional_t3_run_static() -> dict:
    """Bind optional solver evidence without importing SciPy into the core environment."""

    audit = load("artifacts/t3-external-run-audit.json")
    input_path = audit.get("run_path", "")
    if (
        audit.get("schema_version") != "t3-external-run-audit-v1"
        or audit.get("status") != "verified-within-pinned-oscillator-grid"
        or not isinstance(input_path, str)
        or not input_path.startswith("artifacts/t3-external-runs/run-t3-scipy-")
        or Path(input_path).is_absolute()
        or ".." in Path(input_path).parts
        or audit.get("relocated_replay_equal") is not True
        or audit.get("result_tamper_rejected") is not True
        or audit.get("license_tamper_rejected") is not True
        or audit.get("policy_denials") != {"wrong_provider_rejected": True, "out_of_scope_path_rejected": True}
        or audit.get("boundaries") != {"oscillator_fixture": True, "multi_body": False, "real_mission": False, "scientific_validity": False, "publication_ready": False}
    ):
        raise ValueError("optional T3 external Run audit is missing or exceeds its boundary")
    recorded_at = datetime.fromisoformat(audit["recorded_at"].replace("Z", "+00:00"))
    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
        raise ValueError("optional T3 external Run audit timestamp is naive")
    run_dir = (ROOT / input_path).resolve()
    if not run_dir.is_relative_to((ROOT / "artifacts/t3-external-runs").resolve()):
        raise ValueError("optional T3 external Run escaped its artifact directory")
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    saved_input = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    saved_result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    receipt = saved_result.get("receipt")
    if (
        saved_input.get("schema_version") != "t3-scipy-run-input-v1"
        or saved_input.get("provider_id") != "scipy-dop853-v1"
        or saved_result.get("provider_id") != "scipy-dop853-v1"
        or run_dir.name != f"run-t3-scipy-{canonical_hash(saved_input)[:16]}"
        or audit.get("run_id") != run_dir.name
        or not isinstance(receipt, dict)
        or receipt.get("status") != "passed-optional-oscillator-cross-check"
        or receipt.get("summary", {}).get("case_count") != 9
        or not all(receipt.get("checks", {}).values())
        or len(receipt.get("checks", {})) != 7
        or receipt.get("environment") != saved_input.get("provider_provenance")
        or receipt.get("grid") != saved_input.get("grid")
        or receipt.get("gates") != saved_input.get("gates")
        or receipt.get("solver") != saved_input.get("solver")
    ):
        raise ValueError("optional T3 external Run input or solver receipt differs")
    static_audit = load("artifacts/t3-external-scipy.json")
    static_audit.pop("recorded_at", None)
    if receipt != static_audit:
        raise ValueError("optional T3 Run differs from independently recorded SciPy audit")
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    if manifest.schema_version != "replay-manifest-v2":
        raise ValueError("optional T3 external Run manifest is not portable")
    required_sources = {
        "root://scripts/verify_t3_external_run.py", "root://scripts/verify_t3_external_scipy.py",
        "root://docs/T3_EXTERNAL_SOLVER.md", "root://requirements-t3-scipy-win-py312.txt",
        "root://schemas/t3-external-tool-call-v1.json",
    }
    source_refs = {item.path for item in manifest.source_files}
    if (
        not required_sources.issubset(source_refs)
        or any(not ref.startswith("root://") for ref in source_refs)
        or {item.path for item in manifest.evidence_files} != {"run://scipy-license.txt", "run://numpy-license.txt"}
        or saved_input.get("source_snapshot_hash") != canonical_hash([
            (item.path.removeprefix("root://"), item.sha256) for item in manifest.source_files
        ])
    ):
        raise ValueError("optional T3 external Run source or license inventory differs")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl", root=ROOT, bindings=bindings)
    if (
        run.run_id != run_dir.name or run.input_hash != canonical_hash(saved_input)
        or run.status.value != "completed" or run.claims[0].status.value != "unverified"
        or run.policy is None or run.policy.network != "disabled"
        or run.policy.allowed_providers != ["scipy-dop853-v1"]
        or len(run.tools) != 1 or run.tools[0].tool_id != "t3-scipy-dop853-crosscheck-v1"
        or len(run.providers) != 1 or run.providers[0].provider_id != "scipy-dop853-v1"
        or run.environment.get("pinned_wheel_sha256") != audit.get("pinned_wheel_sha256")
        or run.environment.get("installed_license_sha256") != audit.get("license_sha256")
    ):
        raise ValueError("optional T3 external shared Run widened its scope")
    replay = manifest.verify(
        input_payload=saved_input, code_revision=run.code_revision, environment=run.environment,
        seed=run.seed, source_paths=[bindings.resolve(item.path) for item in manifest.source_files],
        evidence_paths=[bindings.resolve(item.path) for item in manifest.evidence_files],
        candidate_order=[], computational_output=receipt, bindings=bindings,
    ).model_dump(mode="json")
    if audit.get("replay") != replay or len(replay["checks"]) != 8:
        raise ValueError("optional T3 external Run audit replay binding differs")
    return replay


def verify_optional_t3_perturbed_static() -> dict:
    """Check receipt scope and source bytes; SciPy recomputation remains a separate command."""

    audit = load("artifacts/t3-perturbed-audit.json")
    expected_sources = {
        "scripts/verify_t3_perturbed.py", "examples/dynamics/nbody-fixture.json",
        "src/auditable_scientist/tracks/nbody.py",
        "src/auditable_scientist/tracks/reference_nbody_rk4.py",
        "scripts/verify_t3_external_scipy.py", "requirements-t3-scipy-win-py312.txt",
        "docs/T3_PERTURBED_METHOD.md",
    }
    rows = audit.get("rows", [])
    checks = audit.get("checks", {})
    if (
        audit.get("schema_version") != "t3-perturbed-audit-v1"
        or audit.get("status") != "passed-optional-finite-horizon-cross-check"
        or audit.get("environment") != load("artifacts/t3-external-scipy.json").get("environment")
        or audit.get("boundaries") != {
            "core_run_evidence": False, "real_ephemerides": False, "mission_validation": False,
            "chaos_or_long_horizon_validation": False, "general_nbody_validity": False,
        }
        or not isinstance(checks, dict) or len(checks) != 11 or not all(value is True for value in checks.values())
        or not isinstance(rows, list) or len(rows) != 2
        or [(row.get("case_id"), row.get("split")) for row in rows]
        != [("equal-train", "train"), ("unequal-holdout", "holdout")]
        or not math.isfinite(audit.get("negative_repulsive_force_error", float("nan")))
        or audit["negative_repulsive_force_error"] < 0.1
        or {item.get("path") for item in audit.get("source_files", [])} != expected_sources
        or len(audit.get("source_files", [])) != len(expected_sources)
    ):
        raise ValueError("optional perturbed T3 receipt is absent or exceeds its bounded scope")
    recorded_at = datetime.fromisoformat(audit["recorded_at"].replace("Z", "+00:00"))
    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
        raise ValueError("optional perturbed T3 receipt timestamp is naive")
    for item in audit["source_files"]:
        path = ROOT / item["path"]
        if item.get("sha256") != fingerprint_file(path).sha256 or item.get("bytes") != path.stat().st_size:
            raise ValueError(f"optional perturbed T3 source differs: {item['path']}")
    return {"scope": "static-source-and-boundary-check-only", "source_files_match": True,
            "pinned_scipy_recomputation_required": True}


def verify_optional_t3_horizon_static(audit: dict | None = None) -> dict:
    """Fail closed on the saved finite-horizon grid without importing SciPy."""

    audit = audit if audit is not None else load("artifacts/t3-horizon-grid-audit.json")
    sources = {
        "scripts/verify_t3_horizon_grid.py", "scripts/verify_t3_perturbed.py",
        "scripts/verify_t3_external_scipy.py", "src/auditable_scientist/tracks/nbody.py",
        "src/auditable_scientist/tracks/reference_nbody_rk4.py",
        "requirements-t3-scipy-win-py312.txt", "docs/T3_HORIZON_GRID.md",
        "examples/dynamics/nbody-fixture.json", "artifacts/t3-perturbed-audit.json",
    }
    identities = [("equal-train", "train"), ("unequal-holdout", "holdout")]
    admitted = audit.get("admitted_rows", [])
    stress = audit.get("excluded_stress_rows", [])
    gates = {
        "fine_verlet_position_error_max": 1e-5,
        "fine_verlet_velocity_error_max": 1e-5,
        "rk4_position_error_max": 1e-8,
        "verlet_convergence_ratio_min": 3.0,
        "relative_energy_drift_max": 1e-5,
        "relative_angular_momentum_drift_max": 1e-10,
        "center_of_mass_drift_max": 1e-10,
        "minimum_sampled_pair_separation_ratio_min": 0.5,
    }
    budget = {"dop853_function_calls_total_max": 12000, "fixed_steps_total_max": 35000}
    boundaries = {
        "smooth_synthetic_0_75_period_grid": True,
        "one_period_stress_cases_admitted": False,
        "chaotic_long_horizon_validated": False,
        "general_nbody_validated": False,
        "real_ephemerides": False,
        "mission_validation": False,
        "publication_ready": False,
        "core_t3_run_changed": False,
    }
    expected_grid = lambda horizon: [
        {"case_id": case_id, "perturbation_fraction": 0.02, "horizon_fraction": horizon}
        for case_id, _ in identities
    ]
    checks = {
        "two_smooth_source_configurations", "fine_verlet_position", "fine_verlet_velocity",
        "rk4_position", "verlet_convergence", "energy_drift", "angular_momentum_drift",
        "center_of_mass_drift", "smooth_separation", "stress_excluded", "compute_budget",
    }
    if (
        audit.get("schema_version") != "t3-horizon-grid-audit-v1"
        or audit.get("status") != "verified-finite-0.75-period-and-stress-rejection"
        or audit.get("scope") != "synthetic momentum-balanced planar three-body initial states; preflight-selected finite grid"
        or audit.get("provider_environment") != load("artifacts/t3-external-scipy.json").get("environment")
        or audit.get("solver") != {
            "reference": "scipy.integrate.solve_ivp:DOP853", "rtol": 1e-12, "atol": 1e-14,
            "max_step_fraction_of_horizon": 1 / 128, "local": "velocity-Verlet",
            "secondary": "independent Cartesian RK4", "event_threshold_ratio": 0.5,
        }
        or audit.get("admitted_grid") != expected_grid(0.75)
        or audit.get("stress_grid") != expected_grid(1.0)
        or audit.get("gates") != gates or audit.get("budget") != budget
        or audit.get("boundaries") != boundaries
        or not isinstance(admitted, list) or not isinstance(stress, list)
        or [(row.get("case_id"), row.get("source_split")) for row in admitted] != identities
        or [(row.get("case_id"), row.get("source_split")) for row in stress] != identities
        or not isinstance(audit.get("checks"), dict)
        or set(audit["checks"]) != checks or not all(value is True for value in audit["checks"].values())
        or len(audit.get("source_files", [])) != len(sources)
        or {item.get("path") for item in audit["source_files"]} != sources
    ):
        raise ValueError("optional T3 horizon grid is missing or exceeds its finite scope")
    recorded_at = datetime.fromisoformat(audit["recorded_at"].replace("Z", "+00:00"))
    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
        raise ValueError("optional T3 horizon grid timestamp is naive")

    def number(row: dict, key: str) -> float:
        value = row.get(key)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError(f"optional T3 horizon grid has invalid {key}")
        return float(value)

    for row in admitted:
        if (number(row, "horizon_fraction") != 0.75
                or number(row, "perturbation_fraction") != 0.02
                or number(row, "coarse_steps") <= 0
                or number(row, "fine_steps") != 2 * number(row, "coarse_steps")
                or number(row, "dop853_function_calls") <= 0
                or not 0 < number(row, "fine_verlet_position_error") <= gates["fine_verlet_position_error_max"]
                or not 0 <= number(row, "fine_verlet_velocity_error") <= gates["fine_verlet_velocity_error_max"]
                or not 0 <= number(row, "rk4_position_error") <= gates["rk4_position_error_max"]
                or number(row, "coarse_verlet_position_error") / number(row, "fine_verlet_position_error")
                != number(row, "verlet_convergence_ratio")
                or number(row, "verlet_convergence_ratio") < gates["verlet_convergence_ratio_min"]
                or not 0 <= number(row, "relative_energy_drift") <= gates["relative_energy_drift_max"]
                or not 0 <= number(row, "relative_angular_momentum_drift") <= gates["relative_angular_momentum_drift_max"]
                or not 0 <= number(row, "center_of_mass_drift") <= gates["center_of_mass_drift_max"]
                or number(row, "sampled_minimum_pair_separation_ratio") <= 0.5
                or row.get("inward_threshold_event_count") != 0):
            raise ValueError("optional T3 admitted horizon row violates its numerical gate")
    for row in stress:
        if (number(row, "horizon_fraction") != 1.0
                or number(row, "perturbation_fraction") != 0.02
                or number(row, "dop853_function_calls") <= 0
                or not 0 < number(row, "sampled_minimum_pair_separation_ratio") < 0.5
                or number(row, "inward_threshold_event_count") < 1
                or not 0 < number(row, "first_inward_event_fraction_of_horizon") < 1
                or row.get("admission") != "excluded-close-approach"):
            raise ValueError("optional T3 stress row was incorrectly admitted")
    observed = audit.get("observed_budget", {})
    nfev = sum(number(row, "dop853_function_calls") for row in [*admitted, *stress])
    fixed = sum(number(row, "coarse_steps") + 2 * number(row, "fine_steps") for row in admitted)
    if (observed != {"dop853_function_calls_total": nfev, "fixed_steps_total": fixed}
            or nfev > budget["dop853_function_calls_total_max"]
            or fixed > budget["fixed_steps_total_max"]):
        raise ValueError("optional T3 horizon grid exceeds its compute budget")
    for item in audit["source_files"]:
        path = ROOT / item["path"]
        if item["path"] == "artifacts/t3-perturbed-audit.json":
            data = path.read_bytes().replace(b"\r\n", b"\n")
            if item.get("normalization") != "crlf-to-lf":
                raise ValueError("optional T3 parent audit line-ending normalization differs")
            source_sha = hashlib.sha256(data).hexdigest()
            source_bytes = len(data)
        else:
            if item.get("normalization") is not None:
                raise ValueError("optional T3 source declares unexpected normalization")
            fingerprint = fingerprint_file(path)
            source_sha, source_bytes = fingerprint.sha256, fingerprint.bytes
        if item.get("sha256") != source_sha or item.get("bytes") != source_bytes:
            raise ValueError(f"optional T3 horizon grid source differs: {item['path']}")
    return {"scope": "static-source-boundary-and-numeric-gate-check-only",
            "source_files_match": True, "pinned_scipy_recomputation_required": True,
            "admitted_case_count": len(admitted), "excluded_stress_case_count": len(stress)}


def verify_optional_t3_perturbed_run_static() -> dict:
    """Verify the optional shared Run and its manifest without importing SciPy."""

    audit = load("artifacts/t3-perturbed-run-audit.json")
    relative = audit.get("run_path", "")
    if (
        audit.get("schema_version") != "t3-perturbed-run-audit-v1"
        or audit.get("status") != "verified-within-pinned-perturbed-grid"
        or not isinstance(relative, str)
        or not relative.startswith("artifacts/t3-perturbed-runs/run-t3-perturbed-")
        or Path(relative).is_absolute() or ".." in Path(relative).parts
        or audit.get("relocated_replay_equal") is not True
        or audit.get("result_tamper_rejected") is not True
        or audit.get("license_tamper_rejected") is not True
        or audit.get("policy_denials") != {"wrong_provider_rejected": True, "out_of_scope_path_rejected": True}
        or audit.get("boundaries") != {
            "synthetic_perturbed_grid": True, "core_t3_run": False,
            "chaotic_long_horizon": False, "real_mission": False,
            "general_nbody_validity": False, "publication_ready": False,
        }
    ):
        raise ValueError("optional perturbed T3 Run audit is missing or exceeds its boundary")
    recorded_at = datetime.fromisoformat(audit["recorded_at"].replace("Z", "+00:00"))
    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
        raise ValueError("optional perturbed T3 Run audit timestamp is naive")
    run_dir = (ROOT / relative).resolve()
    if not run_dir.is_relative_to((ROOT / "artifacts/t3-perturbed-runs").resolve()):
        raise ValueError("optional perturbed T3 Run escaped its artifact directory")
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    saved_input = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    saved_result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    receipt = saved_result.get("receipt")
    static_receipt = load("artifacts/t3-perturbed-audit.json")
    static_receipt.pop("recorded_at", None)
    if (
        saved_input.get("schema_version") != "t3-perturbed-run-input-v1"
        or saved_input.get("track_id") != "T3"
        or saved_input.get("provider_id") != "scipy-dop853-perturbed-v1"
        or saved_result.get("provider_id") != "scipy-dop853-perturbed-v1"
        or run_dir.name != f"run-t3-perturbed-{canonical_hash(saved_input)[:16]}"
        or audit.get("run_id") != run_dir.name
        or not isinstance(receipt, dict) or receipt != static_receipt
        or receipt.get("environment") != saved_input.get("provider_provenance")
        or receipt.get("grid") != saved_input.get("grid")
        or receipt.get("gates") != saved_input.get("gates")
        or receipt.get("solver") != saved_input.get("solver")
    ):
        raise ValueError("optional perturbed T3 Run input or solver receipt differs")
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    required_sources = {
        "root://scripts/verify_t3_perturbed_run.py", "root://scripts/verify_t3_perturbed.py",
        "root://docs/T3_PERTURBED_METHOD.md", "root://requirements-t3-scipy-win-py312.txt",
        "root://schemas/t3-perturbed-tool-call-v1.json", "root://examples/dynamics/nbody-fixture.json",
    }
    source_refs = {item.path for item in manifest.source_files}
    if (
        manifest.schema_version != "replay-manifest-v2"
        or not required_sources.issubset(source_refs)
        or any(not ref.startswith("root://") for ref in source_refs)
        or {item.path for item in manifest.evidence_files} != {"run://scipy-license.txt", "run://numpy-license.txt"}
        or saved_input.get("source_snapshot_hash") != canonical_hash([
            (item.path.removeprefix("root://"), item.sha256) for item in manifest.source_files
        ])
    ):
        raise ValueError("optional perturbed T3 Run source or license inventory differs")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl", root=ROOT, bindings=bindings)
    if (
        run.run_id != run_dir.name or run.input_hash != canonical_hash(saved_input)
        or run.status.value != "completed" or len(run.claims) != 1
        or run.claims[0].status.value != "unverified" or run.claims[0].holdout_verified
        or run.environment.get("subtrack") != "perturbed-three-body"
        or run.policy is None or run.policy.network != "disabled"
        or run.policy.allowed_providers != ["scipy-dop853-perturbed-v1"]
        or len(run.tools) != 1 or run.tools[0].tool_id != "t3-perturbed-three-body-crosscheck-v1"
        or len(run.providers) != 1 or run.providers[0].provider_id != "scipy-dop853-perturbed-v1"
        or run.environment.get("pinned_wheel_sha256") != audit.get("pinned_wheel_sha256")
        or run.environment.get("installed_license_sha256") != audit.get("license_sha256")
    ):
        raise ValueError("optional perturbed T3 shared Run widened its scope")
    replay = manifest.verify(
        input_payload=saved_input, code_revision=run.code_revision,
        environment=run.environment, seed=run.seed,
        source_paths=[bindings.resolve(item.path) for item in manifest.source_files],
        evidence_paths=[bindings.resolve(item.path) for item in manifest.evidence_files],
        candidate_order=[], computational_output=receipt, bindings=bindings,
    ).model_dump(mode="json")
    if audit.get("replay") != replay or len(replay["checks"]) != 8:
        raise ValueError("optional perturbed T3 Run replay binding differs")
    return replay


def verify_check_rows(checks: list[dict], *, root: Path, expected_input: str | None = None) -> None:
    if not checks:
        raise ValueError("acceptance package has no command receipts")
    for check in checks:
        if not check.get("name") or not check.get("command") or check.get("exit_code") != 0:
            raise ValueError("acceptance command is missing, failed, or unnamed")
        if not check.get("input_version") or not check.get("output_path") or not check.get("recorded_at"):
            raise ValueError("acceptance command is missing version, output path, or timestamp")
        timestamp = datetime.fromisoformat(check["recorded_at"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("acceptance timestamp must include a timezone")
        output = Path(check["output_path"])
        if output.is_absolute() or ".." in output.parts or not (root / output).exists():
            raise ValueError("acceptance command result path is missing or unsafe")
        if expected_input is not None and check["input_version"] != expected_input:
            raise ValueError("acceptance command input version differs from fixture hash")


def same_evaluator_receipt_except_source(live: TrackReceipt, saved: dict) -> bool:
    """Compare rerun semantics after historical source bytes are checked separately."""

    def without_source_inventory(payload: dict) -> dict:
        return {key: value for key, value in payload.items() if key != "source_files"}

    return canonical_hash(without_source_inventory(live.model_dump(mode="json"))) == canonical_hash(
        without_source_inventory(saved)
    )


def verify_track_bundle(track_id: str, item: dict, bundle_dir: Path, *, root: Path = ROOT) -> None:
    receipt = TrackReceipt.model_validate(item)
    if receipt.track_id != track_id or not receipt.passed or not receipt.negative_case_passed:
        raise ValueError(f"track {track_id} evaluator gates or identity failed")
    if not receipt.evidence_files or not receipt.source_files:
        raise ValueError(f"track {track_id} has no evidence or source fingerprints")
    for record in [*receipt.evidence_files, *receipt.source_files]:
        relative = Path(record.path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"track {track_id} has an unsafe source or evidence path")
        fingerprint = fingerprint_file(root / relative)
        if ((fingerprint.sha256 != record.sha256 or fingerprint.bytes != record.bytes)
                and not historical_source_matches(record.path, record.sha256, record.bytes)):
            raise ValueError(f"track {track_id} source or evidence changed: {record.path}")
    for filename in ("acceptance.json", "test-report.md", "demo-transcript.md", "sample-run.json", "events.jsonl"):
        if not (bundle_dir / filename).is_file():
            raise ValueError(f"track {track_id} evidence package is missing: {filename}")
    acceptance = json.loads((bundle_dir / "acceptance.json").read_text(encoding="utf-8"))
    schema = json.loads((root / "schemas/track-acceptance-v1.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(acceptance)
    verify_check_rows(acceptance["checks"], root=root)
    for check in acceptance["checks"]:
        special_inputs = {
            "bounded-parameter-step-sweep": "t3-sweep-v1",
            "optional-external-solver-run": "t3-external-run-audit-v1",
            "optional-perturbed-three-body-cross-check": "t3-perturbed-audit-v1",
            "optional-perturbed-three-body-run": "t3-perturbed-run-audit-v1",
            "optional-expanded-horizon-grid": "t3-horizon-grid-audit-v1",
            "symmetric-three-body-subtrack": load("artifacts/t3-nbody/acceptance.json")["evaluator"]["input_hash"],
        } if track_id == "T3" else ({
            "physical-counterfactual-subtrack": load("artifacts/t2-physical/acceptance.json")["evaluator"]["input_hash"],
        } if track_id == "T2" else ({
            "oscillator-physical-module-subtrack": load("artifacts/t4-oscillator/acceptance.json")["evaluator"]["input_hash"],
            "exact-linear-invariant-subtrack": load("artifacts/t4-linear-formal-audit.json")["input_sha256"],
            "exact-linear-invariant-run": load("artifacts/t4-linear-run-audit.json")["run_id"],
        } if track_id == "T4" else ({
            "independent-endpoint-estimator": "t2-independent-endpoint-audit-v1",
            "independent-endpoint-run": load("artifacts/t2-independent-run-audit.json")["run_id"],
        } if track_id == "T2P" else {})))
        expected_input = special_inputs.get(check.get("name"), receipt.input_hash)
        if check["input_version"] != expected_input:
            raise ValueError(f"track {track_id} acceptance command input version differs")
    if acceptance["track"] != track_id or canonical_hash(acceptance["evaluator"]) != canonical_hash(item):
        raise ValueError(f"track {track_id} acceptance package differs from portfolio receipt")
    if acceptance["evidence_boundaries"] != {
        "demo": True,
        "validated_reproduction": item["evidence_level"] == "validated-reproduction",
        "real_data": False,
        "research_candidate": False,
    }:
        raise ValueError(f"track {track_id} evidence boundaries are incomplete")
    sample = json.loads((bundle_dir / "sample-run.json").read_text(encoding="utf-8"))
    if sample.get("track") != track_id or sample.get("input_hash") != item["input_hash"]:
        raise ValueError(f"track {track_id} sample identity differs from receipt")
    for key, expected in (
        ("evaluator", item["result"]),
        ("negative_case", acceptance["negative_case"]),
        ("evidence_files", item["evidence_files"]),
        ("source_files", item["source_files"]),
    ):
        if canonical_hash(sample.get(key)) != canonical_hash(expected):
            raise ValueError(f"track {track_id} sample {key} differs from receipt")
    run_schema = json.loads((root / "schemas/run.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(run_schema).validate(sample["run"])
    run = Run.model_validate(sample["run"])
    if run.input_hash != item["input_hash"] or run.run_id != f"run-{track_id.lower()}-{item['input_hash'][:16]}":
        raise ValueError(f"track {track_id} shared Run differs from receipt")
    if run.agent is None or not run.tools or not run.memories or not run.evaluators or not run.providers or run.policy is None:
        raise ValueError(f"track {track_id} shared kernel records are incomplete")
    if run.policy.network != "disabled" or run.providers[0].provider_id not in run.policy.allowed_providers:
        raise ValueError(f"track {track_id} policy/provider binding is inconsistent")
    if (run.evaluators[0].evaluator_id != receipt.evaluator_id or len(run.claims) != 1
            or run.claims[0].status.value != "unverified"
            or run.claims[0].level.value != receipt.evidence_level):
        raise ValueError(f"track {track_id} evaluator or claim boundary differs from receipt")
    if run.tools[0].parameter_schema_ref != "schemas/track-tool-call-v1.json":
        raise ValueError(f"track {track_id} tool schema reference is inconsistent")
    for evidence in run.evidence:
        path = BoundPaths(root=root, run_dir=bundle_dir).resolve(evidence.path_or_uri)
        if fingerprint_file(path).sha256 != evidence.sha256:
            raise ValueError(f"track {track_id} Run evidence changed: {evidence.evidence_id}")
    evaluator_sources = {record.sha256 for record in receipt.source_files if record.path.endswith(("causal.py", "physical_world.py", "dynamics.py", "reference_rk4.py", "nbody.py", "reference_nbody_rk4.py", "proof.py", "oscillator_proof.py", "dimensions.py", "protocol.py"))}
    if {evidence.sha256 for evidence in run.evidence if evidence.kind.value == "code"} != evaluator_sources:
        raise ValueError(f"track {track_id} Run code evidence differs from source receipt")
    events = EventLog(bundle_dir / "events.jsonl").verify()
    if canonical_hash(events) != canonical_hash(run.events):
        raise ValueError(f"track {track_id} Run events do not match events.jsonl")
    trace_entries = [{"seq": event.seq, "event_type": event.event_type, "payload_hash": event.payload_hash} for event in events]
    if len(run.traces) != 1 or canonical_hash(run.traces[0].entries) != canonical_hash(trace_entries):
        raise ValueError(f"track {track_id} trace differs from events.jsonl")
    required_events = {"run.initialized", "policy.applied", "tool.invoked", "evaluator.completed", "negative_case.checked", "run.completed"}
    by_type = {event.event_type: event for event in events}
    if not required_events.issubset(by_type):
        raise ValueError(f"track {track_id} event lifecycle is incomplete")
    if by_type["run.initialized"].payload != {"run_id": run.run_id, "input_hash": run.input_hash}:
        raise ValueError(f"track {track_id} initialization event differs from Run")
    if by_type["run.completed"].payload.get("status") != run.status.value:
        raise ValueError(f"track {track_id} completion event differs from Run")
    if by_type["tool.invoked"].payload != {"tool_id": run.tools[0].tool_id, "calls_used": 1}:
        raise ValueError(f"track {track_id} did not record one registered evaluator call")
    if by_type["evaluator.completed"].payload != {"evaluator_id": receipt.evaluator_id, "result": item["result"]}:
        raise ValueError(f"track {track_id} evaluator event differs from receipt")
    if by_type["negative_case.checked"].payload != {
        "negative_case": acceptance["negative_case"], "negative_case_passed": receipt.negative_case_passed
    }:
        raise ValueError(f"track {track_id} negative event differs from receipt")


def main() -> None:
    acceptance = load("artifacts/acceptance.json")
    if acceptance["status"] != "accepted-with-bounded-scope":
        raise SystemExit("T1 acceptance status is not bounded acceptance")
    verify_check_rows(acceptance["checks"], root=ROOT)
    projected = subprocess.run(
        [sys.executable, str(ROOT / "scripts/sync_optional_acceptance.py"), "--verify"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if projected.returncode != 0:
        raise SystemExit(f"optional acceptance projection differs: {projected.stderr.strip() or projected.stdout.strip()}")
    projection_receipt = json.loads(projected.stdout)
    nasa_audit = load("artifacts/t1-nasa-factsheet-audit.json")
    nasa_replay = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_t1_nasa_factsheets.py"), "verify"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if (nasa_replay.returncode != 0
            or json.loads(nasa_replay.stdout).get("status") != nasa_audit.get("status")
            or nasa_audit.get("status") != "verified-offline-snapshot-only"
            or nasa_audit.get("source_rights_status") != "unreviewed-page-specific"
            or any(nasa_audit.get(key) is not False for key in (
                "offline_origin_authentication", "real_data_claim", "scientific_validation_claim"
            ))):
        raise SystemExit("T1 NASA parameter audit differs from offline source-row replay or exceeds its boundary")
    if not any(
        item.get("name") == "optional-nasa-factsheet-parameter-sensitivity"
        and item.get("output_path") == "artifacts/t1-nasa-factsheet-audit.json"
        and item.get("input_version") == nasa_audit["snapshot_sha256"]
        for item in acceptance["checks"]
    ):
        raise SystemExit("T1 NASA parameter audit is missing its bounded command receipt")
    t1_core_orbit = verify_core_t1_orbit()
    if not any(
        item.get("name") == "t1-core-offline-orbit-propagation"
        and item.get("output_path") == "artifacts/t1-core-orbit-audit.json"
        and item.get("input_version") == fingerprint_file(ROOT / "scripts/verify_t1_core_orbit.py").sha256
        for item in acceptance["checks"]
    ):
        raise SystemExit("T1 core orbit audit is missing its recomputation receipt")
    t1_core_orbit_run = verify_core_t1_orbit_run()
    if not any(
        item.get("name") == "t1-versioned-core-orbit-tool-run"
        and item.get("output_path") == "artifacts/t1-core-orbit-run-audit.json"
        and item.get("input_version") == fingerprint_file(ROOT / "scripts/verify_t1_core_orbit_run.py").sha256
        for item in acceptance["checks"]
    ):
        raise SystemExit("T1 numerical Tool/Provider Run is missing its replay receipt")
    t1_combined_cli = verify_combined_t1_cli()
    if not any(
        item.get("name") == "t1-combined-package-cli-run"
        and item.get("output_path") == "artifacts/t1-combined-cli-audit-v4.json"
        and item.get("input_version") == fingerprint_file(ROOT / "scripts/verify_t1_combined_cli.py").sha256
        for item in acceptance["checks"]
    ):
        raise SystemExit("T1 v2 package CLI Run is missing its dynamic acceptance receipt")
    de440s = verify_optional_t1_de440s()
    if not any(
        item.get("name") == "optional-t1-de440s-fixed-date-geometry"
        and item.get("output_path") == "artifacts/t1-de440s-ephemeris-audit.json"
        and item.get("input_version") == fingerprint_file(ROOT / "scripts/verify_t1_de440s_ephemeris.py").sha256
        and item.get("exit_code") == 0
        for item in acceptance["checks"]
    ):
        raise SystemExit("T1 DE440s optional geometry audit has no command receipt")
    de440s_run = verify_optional_t1_de440s_run()
    if not any(
        item.get("name") == "optional-t1-de440s-portable-snapshot-run"
        and item.get("output_path") == "artifacts/t1-de440s-run-audit.json"
        and item.get("input_version") == de440s_run["run_id"]
        and item.get("exit_code") == 0
        for item in acceptance["checks"]
    ):
        raise SystemExit("T1 DE440s portable Run has no command receipt")
    mars_center = verify_optional_t1_mars_center()
    if not any(
        item.get("name") == "optional-t1-mars-center-fixed-date-geometry"
        and item.get("output_path") == "artifacts/t1-mars-center-ephemeris-audit.json"
        and item.get("input_version") == fingerprint_file(ROOT / "scripts/verify_t1_mars_center_ephemeris.py").sha256
        and item.get("exit_code") == 0
        for item in acceptance["checks"]
    ):
        raise SystemExit("T1 Mars-center optional geometry audit has no command receipt")
    maven_source = verify_optional_t1_maven_source()
    if not any(
        item.get("name") == "optional-t1-maven-reconstructed-source"
        and item.get("output_path") == "artifacts/t1-maven-source-audit.json"
        and item.get("input_version") == fingerprint_file(ROOT / "scripts/verify_t1_maven_source.py").sha256
        and item.get("exit_code") == 0
        for item in acceptance["checks"]
    ):
        raise SystemExit("T1 MAVEN reconstructed source has no command receipt")
    t1_orbit_static = verify_optional_t1_orbit_static()
    orbit_script_sha = fingerprint_file(ROOT / "scripts/verify_t1_external_orbit.py").sha256
    if not any(
        item.get("name") == "optional-t1-external-orbit-cross-check"
        and item.get("output_path") == "artifacts/t1-external-orbit-audit.json"
        and item.get("input_version") == orbit_script_sha
        for item in acceptance["checks"]
    ):
        raise SystemExit("T1 external orbit audit is missing its pinned dynamic-verification receipt")
    t1_external_run_replay = verify_optional_t1_run_static()
    orbit_run_script_sha = fingerprint_file(ROOT / "scripts/verify_t1_external_orbit_run.py").sha256
    if not any(
        item.get("name") == "optional-t1-external-orbit-tool-run"
        and item.get("output_path") == "artifacts/t1-external-run-audit.json"
        and item.get("input_version") == orbit_run_script_sha
        for item in acceptance["checks"]
    ):
        raise SystemExit("T1 external orbit Run is missing its pinned dynamic-verification receipt")
    symbolic_audit = load("artifacts/symbolic-engine-audit.json")
    symbolic_manifest = next(item for item in built_in_manifests() if item.adapter_id == "symbolic-physics-engine")
    audited_sources = {row["path"]: row for row in symbolic_audit.get("source_files", [])}
    entrypoint = audited_sources.get("src/ai_feynman.py", {})
    if (
        symbolic_audit.get("schema_version") != "external-symbolic-audit-v1"
        or symbolic_audit.get("adapter_status") != "blocked"
        or symbolic_audit.get("execution_allowed") is not False
        or symbolic_audit.get("code_reuse_allowed") is not False
        or symbolic_audit.get("source_tracked_by_parent_git") is not False
        or symbolic_audit.get("source_revision") is not None
        or symbolic_audit.get("entrypoint_unconditionally_raises_not_implemented") is not True
        or symbolic_audit.get("license_files") != []
        or symbolic_audit.get("license_status") != "missing-scoped-license"
        or symbolic_audit.get("source_path") != symbolic_manifest.source_path_or_uri
        or symbolic_manifest.status.value != "blocked"
        or symbolic_manifest.code_reuse_allowed is not False
        or symbolic_manifest.source_revision != f"untracked-entrypoint-sha256:{entrypoint.get('sha256')}"
        or symbolic_audit.get("audit_script_sha256") != fingerprint_file(ROOT / "scripts/audit_symbolic_engine.py").sha256
        or not any(item.get("name") == "read-only-symbolic-source-audit" and item.get("output_path") == "artifacts/symbolic-engine-audit.json" for item in acceptance["checks"])
    ):
        raise SystemExit("external symbolic provider provenance gate was incorrectly promoted")

    run_dir = ROOT / "artifacts/acceptance-runs-v18/run-02a00f229aabd3d2"
    run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    Draft202012Validator(load("schemas/run.schema.json")).validate(run_payload)
    run = Run.model_validate(run_payload)
    if run.agent is None or not run.tools or not run.memories or not run.evaluators or not run.providers or run.policy is None:
        raise SystemExit("T1 run is missing a shared kernel record")
    if run.policy.network != "disabled" or run.providers[0].provider_id not in run.policy.allowed_providers:
        raise SystemExit("T1 policy/provider binding is inconsistent")
    project05_snapshot = Project05Snapshot.model_validate(json.loads((run_dir / "project05-snapshot.json").read_text(encoding="utf-8")))
    if project05_snapshot.status != "blocked" and not Project05Adapter(project05_snapshot.source_path).verify_snapshot(project05_snapshot):
        raise SystemExit("project-05 source snapshot changed")
    t1_events = EventLog(run_dir / "events.jsonl").verify()
    if canonical_hash(t1_events) != canonical_hash(run.events):
        raise SystemExit("T1 run.json events do not match the append-only event log")
    required_t1_events = {
        "run.initialized",
        "plan.created",
        "policy.applied",
        "data.summarized",
        "tool.invoked",
        "candidate_set.committed",
        "holdout.evaluated",
        "calculation.completed",
        "failure.checked",
        "approval.recorded",
        "run.completed",
    }
    if not required_t1_events.issubset({event.event_type for event in t1_events}):
        raise SystemExit("T1 event log is missing a required lifecycle event")
    if not run.traces or canonical_hash(run.traces[0].entries) != canonical_hash(
        [{"seq": event.seq, "event_type": event.event_type, "payload_hash": event.payload_hash} for event in t1_events]
    ):
        raise SystemExit("T1 trace does not cover the event log")
    replay_receipt = ReplayReceipt.model_validate(replay_verified_run(run_dir))
    if not replay_receipt.verified:
        raise SystemExit("T1 replay receipt did not verify")
    if canonical_hash(load("artifacts/sample-run.json")) != canonical_hash(run_payload):
        raise SystemExit("T1 sample run differs from the accepted run")

    portfolio = load("artifacts/track-portfolio.json")
    status = load("artifacts/portfolio-status.json")
    if status.get("public_release_allowed") is not False or status.get("pushed") is not False:
        raise SystemExit("portfolio release boundary is not fail-closed")
    if [item["track_id"] for item in status.get("tracks", [])] != ["T1", "T2", "T3", "T4", "T5"]:
        raise SystemExit("portfolio status table is incomplete")
    if not (ROOT / "artifacts/portfolio-status.md").is_file():
        raise SystemExit("portfolio status markdown is missing")
    if [item["track_id"] for item in portfolio["tracks"]] != ["T1", "T2", "T3", "T4", "T5"]:
        raise SystemExit("portfolio track order or membership is incomplete")
    for track_id in ("T2", "T3", "T4", "T5"):
        item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == track_id)
        directory = {
            "T2": "t2-causal",
            "T3": "t3-dynamics",
            "T4": "t4-proof",
            "T5": "t5-protocol",
        }[track_id]
        bundle_dir = ROOT / "artifacts" / directory
        verify_track_bundle(track_id, item, bundle_dir)
        live = run_registered_track(track_id, ROOT / item["evidence_files"][0]["path"])
        # Historical source bytes are checked against the pinned archive in
        # verify_track_bundle; current rerun compares evaluator output and
        # evidence without pretending the new pyproject is the old source.
        if not same_evaluator_receipt_except_source(live.receipt, item) or live.calls_used != 1:
            raise SystemExit(f"track {track_id} registered evaluator replay differs from receipt")

    physical_acceptance = load("artifacts/t2-physical/acceptance.json")
    physical_item = physical_acceptance["evaluator"]
    verify_track_bundle("T2P", physical_item, ROOT / "artifacts/t2-physical")
    physical_fixture = load("examples/causal/physical-fixture.json")
    if physical_fixture.get("schema_version") != "physical-world-fixture-v1":
        raise SystemExit("T2P fixture version differs")
    physical_cases = [PhysicalCase.model_validate(row) for row in physical_fixture["cases"]]
    physical_evaluation, physical_receipt = evaluate_physical_fixture(physical_cases)
    if (
        [case.model_dump(mode="json") for case in physical_cases] != [case.model_dump(mode="json") for case in standard_cases()]
        or physical_evaluation.model_dump(mode="json") != physical_item["result"]
        or physical_receipt.input_hash != physical_item["input_hash"]
        or not physical_evaluation.ignored_intervention_rejected
        or not same_evaluator_receipt_except_source(
            run_registered_track("T2P", ROOT / "examples/causal/physical-fixture.json").receipt,
            physical_item,
        )
        or load("artifacts/t2-physical/counterfactual-example.json") != compare(physical_cases[3]).model_dump(mode="json")
    ):
        raise SystemExit("T2P physical counterfactual replay mismatch")
    t2_endpoint_audit = load("artifacts/t2-independent-endpoint-audit.json")
    t2_endpoint_replay = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_t2_independent_endpoint.py"), "--verify"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if t2_endpoint_replay.returncode != 0:
        raise SystemExit(f"T2 independent endpoint replay failed: {t2_endpoint_replay.stderr.strip()}")
    t2_endpoint_output = json.loads(t2_endpoint_replay.stdout)
    if (
        t2_endpoint_audit.get("schema_version") != "t2-independent-endpoint-audit-v1"
        or t2_endpoint_audit.get("status") != "verified-synthetic-endpoints-only"
        or t2_endpoint_audit.get("case_count") != 124
        or t2_endpoint_audit.get("train_count") != 40
        or t2_endpoint_audit.get("holdout_count") != 84
        or len(t2_endpoint_audit.get("rows", [])) != 124
        or not all(t2_endpoint_audit.get("gates", {}).values())
        or t2_endpoint_output != {
            "status": "verified-synthetic-endpoints-only",
            "case_count": 124,
            "gates": t2_endpoint_audit["gates"],
        }
        or t2_endpoint_audit.get("boundaries") != {
            "synthetic_simulator_endpoints": True,
            "independent_event_interval_implementation": True,
            "observational_causal_identification": False,
            "real_intervention_data": False,
            "physical_model_validated": False,
            "source_rights_reviewed": False,
            "research_candidate": False,
            "publication_ready": False,
        }
        or not any(
            item.get("name") == "independent-endpoint-estimator"
            and item.get("output_path") == "artifacts/t2-independent-endpoint-audit.json"
            and item.get("input_version") == "t2-independent-endpoint-audit-v1"
            for item in physical_acceptance["checks"]
        )
    ):
        raise SystemExit("T2 independent endpoint audit or boundary differs")
    t2_endpoint_run = load("artifacts/t2-independent-run-audit.json")
    t2_endpoint_run_replay = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_t2_independent_run.py"), "--verify"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if t2_endpoint_run_replay.returncode != 0:
        raise SystemExit(f"T2 independent endpoint Run failed: {t2_endpoint_run_replay.stderr.strip()}")
    t2_endpoint_run_output = json.loads(t2_endpoint_run_replay.stdout)
    if (
        t2_endpoint_run.get("schema_version") != "t2-independent-run-audit-v1"
        or t2_endpoint_run_output.get("status") != "verified-synthetic-endpoint-run-only"
        or t2_endpoint_run_output.get("run_id") != t2_endpoint_run["run_id"]
        or t2_endpoint_run_output.get("replay") != t2_endpoint_run["replay"]
        or t2_endpoint_run_output.get("mutation_controls") != [True, True]
        or t2_endpoint_run.get("relocated_replay_equal") is not True
        or t2_endpoint_run.get("policy_denials") != {
            "wrong_provider_rejected": True, "out_of_scope_path_rejected": True,
        }
        or t2_endpoint_run.get("boundaries") != t2_endpoint_audit["boundaries"]
        or not any(
            item.get("name") == "independent-endpoint-run"
            and item.get("output_path") == "artifacts/t2-independent-run-audit.json"
            and item.get("input_version") == t2_endpoint_run["run_id"]
            for item in physical_acceptance["checks"]
        )
    ):
        raise SystemExit("T2 independent endpoint Run binding or boundary differs")

    nbody_acceptance = load("artifacts/t3-nbody/acceptance.json")
    nbody_item = nbody_acceptance["evaluator"]
    verify_track_bundle("T3N", nbody_item, ROOT / "artifacts/t3-nbody")
    nbody_fixture = load("examples/dynamics/nbody-fixture.json")
    if nbody_fixture.get("schema_version") != "nbody-fixture-v1":
        raise SystemExit("T3N fixture version differs")
    nbody_cases = [NBodyCase.model_validate(row) for row in nbody_fixture["cases"]]
    nbody_evaluation, nbody_receipt = evaluate_nbody_fixture(nbody_cases)
    if (
        nbody_evaluation.model_dump(mode="json") != nbody_item["result"]
        or nbody_receipt.input_hash != nbody_item["input_hash"]
        or not nbody_evaluation.negative_force_rejected
        or not same_evaluator_receipt_except_source(
            run_registered_track("T3N", ROOT / "examples/dynamics/nbody-fixture.json").receipt,
            nbody_item,
        )
    ):
        raise SystemExit("T3N analytic and numerical evaluator replay mismatch")

    t2_item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T2")
    t2_fixture = load("examples/causal/fixture.json")
    t2_cases = [CausalCase.model_validate(item) for item in t2_fixture["cases"]]
    t2_eval, t2_receipt = evaluate_causal_fixture(t2_cases)
    if t2_eval.model_dump(mode="json") != t2_item["result"] or t2_receipt.input_hash != t2_item["input_hash"] or not t2_receipt.negative_case_passed:
        raise SystemExit("T2 evaluator replay mismatch")
    t2_negative = load("artifacts/t2-causal/acceptance.json")["negative_case"]
    t2_bad_eval, _ = evaluate_causal_fixture(t2_cases, negative_coefficient=t2_negative["wrong_coefficient"])
    if t2_negative != {"wrong_coefficient": t2_negative["wrong_coefficient"], "rejected": t2_bad_eval.negative_candidate_rejected} or t2_negative["wrong_coefficient"] == t2_eval.coefficient or not t2_bad_eval.negative_candidate_rejected:
        raise SystemExit("T2 negative case replay mismatch")
    if not any(item.get("name") == "physical-counterfactual-subtrack" and item.get("output_path") == "artifacts/t2-physical/acceptance.json" for item in load("artifacts/t2-causal/acceptance.json")["checks"]):
        raise SystemExit("T2 physical counterfactual subtrack is missing from acceptance")

    t3_item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T3")
    t3_fixture = load("examples/dynamics/fixture.json")
    t3_cases = [DynamicsCase.model_validate(item) for item in t3_fixture["cases"]]
    t3_eval, t3_receipt = evaluate_dynamics_fixture(t3_cases)
    if t3_eval.model_dump(mode="json") != t3_item["result"] or t3_receipt.input_hash != t3_item["input_hash"] or not t3_receipt.negative_case_passed:
        raise SystemExit("T3 evaluator replay mismatch")
    if load("artifacts/t3-dynamics/acceptance.json")["negative_case"] != {"solver": "explicit-euler", "rejected": t3_eval.negative_euler_rejected}:
        raise SystemExit("T3 negative case replay mismatch")
    t3_checks = load("artifacts/t3-dynamics/acceptance.json")["checks"]
    if not any(item.get("name") == "bounded-parameter-step-sweep" and item.get("output_path") == "artifacts/t3-sweep.json" for item in t3_checks):
        raise SystemExit("T3 parameter sweep is missing from acceptance")
    sweep = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_t3_sweep.py"), "--verify"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if sweep.returncode != 0:
        raise SystemExit(f"T3 parameter sweep replay failed: {sweep.stderr.strip()}")
    if not any(item.get("name") == "optional-external-solver-run" and item.get("output_path") == "artifacts/t3-external-run-audit.json" for item in t3_checks):
        raise SystemExit("optional T3 external Run is missing from acceptance")
    if not any(item.get("name") == "symmetric-three-body-subtrack" and item.get("output_path") == "artifacts/t3-nbody/acceptance.json" for item in t3_checks):
        raise SystemExit("T3 symmetric three-body subtrack is missing from acceptance")
    if not any(item.get("name") == "optional-perturbed-three-body-cross-check" and item.get("output_path") == "artifacts/t3-perturbed-audit.json" for item in t3_checks):
        raise SystemExit("T3 perturbed cross-check is missing from acceptance")
    if not any(item.get("name") == "optional-perturbed-three-body-run" and item.get("output_path") == "artifacts/t3-perturbed-run-audit.json" for item in t3_checks):
        raise SystemExit("T3 optional perturbed Run is missing from acceptance")
    if not any(item.get("name") == "optional-expanded-horizon-grid" and item.get("output_path") == "artifacts/t3-horizon-grid-audit.json" for item in t3_checks):
        raise SystemExit("T3 optional expanded horizon grid is missing from acceptance")
    if not any(item.get("name") == "optional-t3-expanded-horizon-grid"
               and item.get("output_path") == "artifacts/t3-horizon-grid-audit.json"
               and item.get("input_version") == "t3-horizon-grid-audit-v1"
               for item in acceptance["checks"]):
        raise SystemExit("T3 expanded horizon grid is missing from root acceptance")
    optional_t3_static_replay = verify_optional_t3_run_static()
    optional_t3_perturbed_static = verify_optional_t3_perturbed_static()
    optional_t3_perturbed_run_static = verify_optional_t3_perturbed_run_static()
    optional_t3_horizon_static = verify_optional_t3_horizon_static()

    t4_item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T4")
    t4_package = ProofPackage.model_validate(load("examples/proof/fixture.json"))
    t4_result = verify_proof_package(t4_package)
    changed_state = t4_package.trajectory[-1].model_copy(update={"mass_b": t4_package.trajectory[-1].mass_b + 1})
    changed_trajectory = [*t4_package.trajectory[:-1], changed_state]
    t4_tampered = t4_package.model_copy(update={
        "trajectory": changed_trajectory,
        "trajectory_hash": canonical_hash([item.model_dump(mode="json") for item in changed_trajectory]),
    })
    if t4_result.model_dump(mode="json") != t4_item["result"] or t4_item["input_hash"] != canonical_hash(t4_package.model_dump(mode="json")) or verify_proof_package(t4_tampered).passed:
        raise SystemExit("T4 proof evaluator replay mismatch")
    if load("artifacts/t4-proof/acceptance.json")["negative_case"] != verify_proof_package(t4_tampered).model_dump(mode="json"):
        raise SystemExit("T4 negative case replay mismatch")
    t4_linear_audit = load("artifacts/t4-linear-formal-audit.json")
    t4_linear_expected = {"verified": True, "systems": 3, "positive_proofs": 2, "negative_controls": 1}
    for command in (
        [sys.executable, str(ROOT / "scripts/check_t4_linear_certificate.py")],
        [sys.executable, str(ROOT / "scripts/verify_t4_linear_formal.py"), "--verify"],
    ):
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        if process.returncode != 0 or json.loads(process.stdout) != t4_linear_expected:
            raise SystemExit(f"T4 exact linear-invariant certificate failed: {process.stderr.strip()}")
    if not any(
        item.get("name") == "exact-linear-invariant-subtrack"
        and item.get("output_path") == "artifacts/t4-linear-formal-audit.json"
        and item.get("input_version") == t4_linear_audit["input_sha256"]
        for item in load("artifacts/t4-proof/acceptance.json")["checks"]
    ):
        raise SystemExit("T4 exact linear-invariant proof is missing from track acceptance")
    t4_linear_run = load("artifacts/t4-linear-run-audit.json")
    t4_linear_run_replay = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_t4_linear_run.py"), "--verify"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if t4_linear_run_replay.returncode != 0:
        raise SystemExit(f"T4 exact linear-invariant Run failed: {t4_linear_run_replay.stderr.strip()}")
    t4_linear_run_output = json.loads(t4_linear_run_replay.stdout)
    if (
        t4_linear_run_output.get("status") != "verified-exact-linear-class-only"
        or t4_linear_run_output.get("run_id") != t4_linear_run["run_id"]
        or t4_linear_run_output.get("replay") != t4_linear_run["replay"]
        or t4_linear_run_output.get("mutation_controls") != [True, True]
        or t4_linear_run.get("relocated_replay_equal") is not True
        or t4_linear_run.get("policy_denials") != {
            "wrong_provider_rejected": True, "out_of_scope_path_rejected": True,
        }
        or t4_linear_run.get("boundaries") != {
            "declared_exact_linear_class": True,
            "physical_model_validated": False,
            "general_formal_backend": False,
            "real_data": False,
            "research_candidate": False,
            "publication_ready": False,
        }
        or not any(
            item.get("name") == "exact-linear-invariant-run"
            and item.get("output_path") == "artifacts/t4-linear-run-audit.json"
            and item.get("input_version") == t4_linear_run["run_id"]
            for item in load("artifacts/t4-proof/acceptance.json")["checks"]
        )
    ):
        raise SystemExit("T4 exact linear-invariant Run binding or boundary differs")
    t4o_acceptance = load("artifacts/t4-oscillator/acceptance.json")
    t4o_item = t4o_acceptance["evaluator"]
    verify_track_bundle("T4O", t4o_item, ROOT / "artifacts/t4-oscillator")
    t4o_package = OscillatorProofPackage.model_validate(load("examples/proof/oscillator-fixture.json"))
    t4o_result = verify_oscillator_package(t4o_package)
    t4o_altered_output = t4o_package.output.model_copy(update={"final_x": t4o_package.output.final_x + 0.1})
    t4o_tampered = t4o_package.model_copy(update={
        "output": t4o_altered_output,
        "output_hash": canonical_hash(t4o_altered_output.model_dump(mode="json")),
    })
    t4o_negative = verify_oscillator_package(t4o_tampered)
    if (
        t4o_result.model_dump(mode="json") != t4o_item["result"]
        or t4o_item["input_hash"] != canonical_hash(t4o_package.model_dump(mode="json"))
        or not t4o_result.passed or t4o_negative.passed
        or t4o_acceptance["negative_case"] != t4o_negative.model_dump(mode="json")
        or not same_evaluator_receipt_except_source(
            run_registered_track("T4O", ROOT / "examples/proof/oscillator-fixture.json").receipt,
            t4o_item,
        )
    ):
        raise SystemExit("T4O oscillator proof evaluator replay mismatch")
    if not any(item.get("name") == "oscillator-physical-module-subtrack" and item.get("output_path") == "artifacts/t4-oscillator/acceptance.json" for item in load("artifacts/t4-proof/acceptance.json")["checks"]):
        raise SystemExit("T4O subtrack is missing from T4 acceptance")

    t5_item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T5")
    t5_protocol = ProtocolSpec.model_validate(load("examples/protocol/fixture.json"))
    t5_result = verify_protocol(t5_protocol)
    t5_changed_document = t5_protocol.documents[0].model_copy(update={
        "text": t5_protocol.documents[0].text.replace("buffer", "water", 1),
    })
    t5_bad = t5_protocol.model_copy(update={"documents": [t5_changed_document, *t5_protocol.documents[1:]]})
    if (
        t5_result.model_dump(mode="json") != t5_item["result"]
        or t5_item["input_hash"] != canonical_hash(t5_protocol.model_dump(mode="json"))
        or not t5_result.passed or verify_protocol(t5_bad).passed
        or t5_result.review_status != "text-reviewed"
        or t5_result.evidence_level != "demo"
        or t5_result.execution_allowed is not False
        or t5_result.requires_human_review is not True
        or any(document.provenance_status != "unverified" for document in t5_protocol.documents)
    ):
        raise SystemExit("T5 protocol evaluator replay mismatch")
    if load("artifacts/t5-protocol/acceptance.json")["negative_case"] != verify_protocol(t5_bad).model_dump(mode="json"):
        raise SystemExit("T5 negative case replay mismatch")
    t1 = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T1")
    t1_experiment = json.loads((run_dir / "experiment.json").read_text(encoding="utf-8"))
    if (
        t1_experiment.get("grammar_version") != GRAMMAR_VERSION
        or len(t1_experiment.get("candidates", [])) != 10
        or t1_experiment.get("selected_candidate_id") != t1["result"]["selected_candidate_id"]
        or t1_experiment.get("candidate_order") != [item["candidate_id"] for item in t1_experiment["candidates"]]
    ):
        raise SystemExit("T1 bounded grammar or portfolio selection differs from replayed experiment")
    for evidence in t1["evidence_files"]:
        path = ROOT / evidence["path"]
        fingerprint = fingerprint_file(path)
        if fingerprint.sha256 != evidence["sha256"] or fingerprint.bytes != evidence["bytes"]:
            raise SystemExit(f"T1 evidence changed: {evidence['path']}")
    t5 = load("artifacts/t5-protocol/acceptance.json")
    if t5["evaluator"]["result"]["execution_allowed"] is not False:
        raise SystemExit("T5 execution boundary was widened")

    cli_replays: dict[str, dict] = {}
    for track_id in ("T2", "T2P", "T3", "T3N", "T4", "T4O", "T5"):
        item = physical_item if track_id == "T2P" else nbody_item if track_id == "T3N" else t4o_item if track_id == "T4O" else next(entry for entry in portfolio["tracks"] if entry["track_id"] == track_id)
        run_dir = ROOT / "artifacts/track-runs-v16" / f"run-{track_id.lower()}-{item['input_hash'][:16]}"
        saved_result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
        def without_paths(receipt: dict) -> dict:
            return {
                **{key: value for key, value in receipt.items() if key != "source_files"},
                "evidence_files": [{**record, "path": "<bound>"} for record in receipt["evidence_files"]],
            }
        # Saved source bytes are checked by the versioned replay; regeneration
        # records the current source inventory, which can include newer CLI files.
        if canonical_hash(without_paths(saved_result["receipt"])) != canonical_hash(without_paths(item)):
            raise SystemExit(f"track {track_id} CLI Run receipt differs from portfolio")
        cli_replays[track_id] = replay_verified_run(run_dir)

    relocation = load("artifacts/relocation-audit.json")
    if (
        relocation.get("status") != "verified-in-recorded-environment"
        or relocation.get("copied_checkout") is not True
        or relocation.get("original_examples_copied") is not False
        or relocation.get("copied_module_imported") is not True
        or relocation.get("tampered_t3_fixture_rejected") is not True
        or relocation.get("script_sha256") != fingerprint_file(ROOT / "scripts/verify_committed_relocation.py").sha256
        or canonical_hash(relocation.get("runs_replayed")) != canonical_hash({"T1": replay_receipt.model_dump(mode="json"), **cli_replays})
    ):
        raise SystemExit("relocation audit is missing or differs from the current five run packages")

    environment_audit = load("artifacts/replay-environment-audit.json")
    constraints = ROOT / "requirements-replay-win-py312.txt"
    pins = {}
    for line in constraints.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            if line.count("==") != 1:
                raise SystemExit("replay environment constraint is not an exact version")
            name, version = line.split("==")
            pins[re.sub(r"[-_.]+", "-", name).lower()] = version
    manifest_paths = {"T1": ROOT / "artifacts/acceptance-runs-v18/run-02a00f229aabd3d2/replay-manifest.json"}
    for track_id in ("T2", "T2P", "T3", "T3N", "T4", "T4O", "T5"):
        receipt = physical_item if track_id == "T2P" else nbody_item if track_id == "T3N" else t4o_item if track_id == "T4O" else next(item for item in portfolio["tracks"] if item["track_id"] == track_id)
        run_id = f"run-{track_id.lower()}-{receipt['input_hash'][:16]}"
        manifest_paths[track_id] = ROOT / "artifacts/track-runs-v16" / run_id / "replay-manifest.json"
    manifest_hashes = {track_id: hashlib.sha256(path.read_bytes()).hexdigest() for track_id, path in manifest_paths.items()}
    if (
        environment_audit.get("schema_version") != "replay-environment-audit-v1"
        or environment_audit.get("status") != "matched-committed-replay-environment"
        or environment_audit.get("isolated_venv") is not True
        or environment_audit.get("platform") != {key: run.environment[key] for key in ("python", "implementation", "system", "machine")}
        or environment_audit.get("installed_packages") != {**pins, "auditable-scientist-lab": "0.1.0"}
        or environment_audit.get("constraints_sha256") != hashlib.sha256(constraints.read_bytes()).hexdigest()
        or environment_audit.get("manifest_sha256") != manifest_hashes
        or environment_audit.get("script_sha256") != fingerprint_file(ROOT / "scripts/verify_replay_environment.py").sha256
    ):
        raise SystemExit("fresh replay environment audit is missing or differs from current inputs")

    wheel = load("artifacts/wheel-audit.json")
    if (
        wheel.get("schema_version") != "wheel-audit-v6"
        or wheel.get("status") != "verified-within-offline-fixtures"
        or wheel.get("checkout_root_in_installed_process") is not None
        or wheel.get("all_nine_relocated_replays_equal") is not True
        or wheel.get("all_nine_committed_console_replays_verified") is not True
        or wheel.get("t1v2_combined_run_and_unverified_mission_claim") is not True
        or wheel.get("t4_bounded_result_and_unverified_run_claim") is not True
        or wheel.get("t4o_bounded_result_and_unverified_run_claim") is not True
        or wheel.get("t5_demo_text_review_and_unverified_run_claim") is not True
        or wheel.get("bundled_resource_count", 0) < 25
        or wheel.get("python") != run.environment["python"]
        or wheel.get("wheel_artifact_committed") is not False
        or set(wheel.get("replay_manifest_hashes", {})) != {"T1", "T1V2", "T2", "T2P", "T3", "T3N", "T4", "T4O", "T5"}
        or set(wheel.get("committed_manifest_hashes", {})) != {"T1", "T1V2", "T2", "T2P", "T3", "T3N", "T4", "T4O", "T5"}
        or wheel.get("source_snapshot_sha256") != wheel_source_snapshot_hash()
        or wheel.get("script_sha256") != fingerprint_file(ROOT / "scripts/verify_wheel_install.py").sha256
        or not re.fullmatch(r"[a-f0-9]{64}", wheel.get("wheel_sha256", ""))
        or any(wheel.get("boundaries", {}).get(key) is not False for key in ("scientific_validity", "real_data", "research_candidate", "publication_ready", "public_release"))
    ):
        raise SystemExit("wheel audit is missing or differs from the current package")

    result = {
        "schema_version": "acceptance-verification-v1",
        "status": "verified",
        "t1_replay": replay_receipt.model_dump(mode="json"),
        "run_status": run.status.value,
        "tracks": [item["track_id"] for item in portfolio["tracks"]],
        "track_evaluators_replayed": ["T2", "T2P", "T3", "T3N", "T4", "T4O", "T5"],
        "track_cli_replays": cli_replays,
        "t3_optional_external_run_static_replay": optional_t3_static_replay,
        "t3_perturbed_static_provenance": optional_t3_perturbed_static,
        "t3_optional_perturbed_run_static_replay": optional_t3_perturbed_run_static,
        "t3_optional_horizon_static_provenance": optional_t3_horizon_static,
        "bounded_optional_acceptance_projection": projection_receipt,
        "wheel_audit_verified": True,
        "t1_nasa_parameter_audit": {
            "status": nasa_audit["status"],
            "snapshot_sha256": nasa_audit["snapshot_sha256"],
            "source_rights_status": nasa_audit["source_rights_status"],
            "real_data_claim": nasa_audit["real_data_claim"],
            "scientific_validation_claim": nasa_audit["scientific_validation_claim"],
        },
        "t1_optional_orbit_static_provenance": t1_orbit_static,
        "t1_core_orbit_recomputation": t1_core_orbit,
        "t1_core_orbit_tool_run": t1_core_orbit_run,
        "t1_combined_package_cli": t1_combined_cli,
        "t1_de440s_geometry": de440s,
        "t1_de440s_snapshot_run": de440s_run,
        "t1_mars_center_geometry": mars_center,
        "t1_maven_reconstructed_source": maven_source,
        "t1_optional_external_run_static_replay": t1_external_run_replay,
        "t2_independent_endpoint_estimator": {
            "case_count": t2_endpoint_audit["case_count"],
            "holdout_count": t2_endpoint_audit["holdout_count"],
            "metrics": t2_endpoint_audit["metrics"],
            "gates": t2_endpoint_audit["gates"],
        },
        "t2_independent_endpoint_run": {
            "run_id": t2_endpoint_run["run_id"],
            "replay": t2_endpoint_run["replay"],
            "mutation_controls": t2_endpoint_run_output["mutation_controls"],
            "policy_denials": t2_endpoint_run["policy_denials"],
        },
        "t4_exact_linear_invariant_proof": t4_linear_expected,
        "t4_exact_linear_invariant_run": {
            "run_id": t4_linear_run["run_id"],
            "replay": t4_linear_run["replay"],
            "mutation_controls": t4_linear_run_output["mutation_controls"],
            "policy_denials": t4_linear_run["policy_denials"],
        },
        "scientific_boundaries": portfolio["global_boundaries"],
    }
    destination = ROOT / "artifacts/acceptance-verification.json"
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
