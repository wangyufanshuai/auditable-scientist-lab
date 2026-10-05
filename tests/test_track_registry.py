"""The track registry must remain complete and fail closed."""

from copy import deepcopy
import json
from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest
from jsonschema.exceptions import ValidationError

from auditable_scientist import track_registry as registry_api

from scripts import verify_track_registry


def test_registry_is_bound_to_current_portfolio() -> None:
    result = verify_track_registry.verify_saved()
    assert result["status"] == "verified-bounded-track-registry"
    assert result["track_ids"] == ["T1", "T2", "T3", "T4", "T5"]
    assert result["boundaries"]["public_release_allowed"] is False


@pytest.mark.parametrize("mutation", ["track", "boundary", "receipt", "typed-boundary"])
def test_registry_rejects_tampering(mutation: str) -> None:
    saved = json.loads(verify_track_registry.AUDIT.read_text(encoding="utf-8"))
    changed = deepcopy(saved)
    if mutation == "track":
        changed["track_ids"] = ["T1", "T2", "T3", "T4"]
    elif mutation == "boundary":
        changed["boundaries"]["public_release_allowed"] = True
    elif mutation == "typed-boundary":
        changed["boundaries"]["public_release_allowed"] = 0
    else:
        changed["required_receipt_count"] += 1
    with pytest.raises(ValueError, match="audit differs"):
        verify_track_registry.verify_saved(changed)


def test_registry_rejects_missing_required_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = json.loads(verify_track_registry.REGISTRY.read_text(encoding="utf-8"))
    registry["tracks"][0]["required_receipts"].append("artifacts/does-not-exist.json")
    registry_path = tmp_path / "TRACK_REGISTRY.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(verify_track_registry, "REGISTRY", registry_path)
    with pytest.raises(ValueError, match="missing or unsafe"):
        verify_track_registry.evaluate()


@pytest.fixture
def evidence_root(tmp_path: Path) -> Path:
    registry = registry_api.bundled_registry()
    paths = {ref for track in registry["tracks"] for ref in track["required_receipts"]}
    paths.update(verify_track_registry.SOURCES)
    paths.add("artifacts/track-registry-audit.json")
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(verify_track_registry.ROOT / relative, target)
    return tmp_path


@pytest.mark.parametrize("field", ["question", "observables", "candidate_space", "baselines", "holdout"])
def test_registration_requires_scientific_problem_contract(field: str) -> None:
    registry = registry_api.bundled_registry()
    del registry["tracks"][0]["problem"][field]
    with pytest.raises(ValidationError):
        registry_api.validate_contract(registry)


@pytest.mark.parametrize("mutation", ["unit", "limit", "global", "release", "rights", "review-reference"])
def test_declarations_reject_missing_units_and_boundary_promotion(mutation: str) -> None:
    registry = registry_api.bundled_registry()
    track = registry["tracks"][0]
    if mutation == "unit":
        track["problem"]["observables"][0]["unit"] = ""
    elif mutation == "limit":
        track["problem"]["candidate_space"]["max_candidates"] = 0
    elif mutation == "global":
        registry["global_boundaries"]["scientific_validity"] = True
    elif mutation == "release":
        track["public_release"] = True
    elif mutation == "rights":
        track["source_rights_status"] = "approved"
    else:
        track["review_evidence"]["source_rights"] = ["docs/unbound-review.json"]
    with pytest.raises((ValidationError, ValueError)):
        registry_api.validate_contract(registry)


def test_duplicate_registry_id_is_rejected() -> None:
    registry = registry_api.bundled_registry()
    registry["tracks"].append(deepcopy(registry["tracks"][0]))
    with pytest.raises(ValueError, match="duplicate registry"):
        registry_api.validate_contract(registry)


@pytest.mark.parametrize("kind", ["source_rights", "human_review"])
def test_review_annotations_cannot_lose_evidence_references(kind: str) -> None:
    registry = registry_api.bundled_registry()
    target = registry["tracks"][0 if kind == "source_rights" else 4]
    target["review_evidence"][kind] = []
    with pytest.raises(ValueError, match="needs evidence references"):
        registry_api.validate_contract(registry)


@pytest.mark.parametrize("relative", ["artifacts/portfolio-status.json", "artifacts/track-portfolio.json"])
def test_duplicate_portfolio_ids_are_not_masked(relative: str, evidence_root: Path) -> None:
    payload = registry_api.load_json((evidence_root / relative).read_text(encoding="utf-8"))
    payload["tracks"].append(deepcopy(payload["tracks"][0]))
    with pytest.raises(ValueError, match="duplicate or invalid"):
        registry_api.validate_evidence(registry_api.bundled_registry(), evidence_root,
                                       overrides={relative: registry_api.canonical_bytes(payload)})


def test_acceptance_cannot_substitute_another_evaluator(evidence_root: Path) -> None:
    relative = "artifacts/t2-causal/acceptance.json"
    payload = registry_api.load_json((evidence_root / relative).read_text())
    payload["evaluator"]["evaluator_id"] = "unreviewed-replacement-v1"
    with pytest.raises(ValueError, match="acceptance evaluator"):
        registry_api.validate_evidence(registry_api.bundled_registry(), evidence_root,
                                       overrides={relative: registry_api.canonical_bytes(payload)})


@pytest.mark.parametrize("relative", ["artifacts/sample-run.json", "artifacts/t2-causal/acceptance.json",
                                     "artifacts/acceptance.json", "docs/T1_MAVEN_MISSION_SOURCE.md"])
def test_saved_audit_rejects_changed_evidence_bytes(relative: str) -> None:
    content = (verify_track_registry.ROOT / relative).read_bytes()
    if relative == "artifacts/acceptance.json":
        payload = registry_api.load_json(content.decode("utf-8"))
        payload["checks"][0]["input_version"] = "changed-source"
        content = registry_api.canonical_bytes(payload)
    else:
        content += b"\n"
    with pytest.raises(ValueError, match="audit differs"):
        verify_track_registry.verify_saved(overrides={relative: content})


@pytest.mark.parametrize("path", ["../outside.json", "artifacts/../docs/x.json", "/artifacts/a.json",
                                  "C:/secret.json", "artifacts\\a.json", "artifacts/a.json:stream",
                                  "artifacts//a.json", "artifacts/a.json.", "artifacts/CON.json"])
def test_unsafe_evidence_paths_are_rejected(path: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsafe"):
        registry_api.safe_file(tmp_path, path)


def test_hard_linked_receipt_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "outside.json"
    source.write_text("{}", encoding="utf-8")
    target = tmp_path / "artifacts/receipt.json"
    target.parent.mkdir()
    os.link(source, target)
    with pytest.raises(ValueError, match="hard-linked"):
        registry_api.safe_file(tmp_path, "artifacts/receipt.json")


def test_linked_receipt_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "outside.json"
    source.write_text("{}", encoding="utf-8")
    target = tmp_path / "artifacts/receipt.json"
    target.parent.mkdir()
    try:
        target.symlink_to(source)
    except OSError:
        if os.name != "nt":
            raise
        junction = tmp_path / "artifacts/linked"
        linked_source = tmp_path / "linked-source"
        linked_source.mkdir()
        (linked_source / "outside.json").write_text("{}", encoding="utf-8")
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(linked_source)],
                                capture_output=True, check=False)
        assert result.returncode == 0
        with pytest.raises(ValueError, match="linked"):
            registry_api.safe_file(tmp_path, "artifacts/linked/outside.json")
    else:
        with pytest.raises(ValueError, match="linked"):
            registry_api.safe_file(tmp_path, "artifacts/receipt.json")


def test_new_target_requires_matching_acceptance_and_portfolio(evidence_root: Path) -> None:
    registry = registry_api.bundled_registry()
    extension = deepcopy(registry["tracks"][1])
    extension.update(track_id="T6", acceptance="artifacts/t6/acceptance.json", evaluator_id="extension-fixture-v1")
    extension["required_receipts"] = [extension["acceptance"]]
    extension["review_evidence"] = {"source_rights": [], "human_review": []}
    registry["tracks"].append(extension)
    assert registry_api.validate_contract(registry)[-1] == "T6"
    with pytest.raises(ValueError, match="membership differs"):
        registry_api.validate_evidence(registry, evidence_root)
    status = registry_api.load_json((evidence_root / "artifacts/portfolio-status.json").read_text())
    status["tracks"].append({key: extension[key] for key in ("track_id", "acceptance", "state", "next_step", "open_gates", "public_release")})
    portfolio = registry_api.load_json((evidence_root / "artifacts/track-portfolio.json").read_text())
    evaluator = deepcopy(portfolio["tracks"][1])
    evaluator.update(track_id="T6", evaluator_id=extension["evaluator_id"])
    portfolio["tracks"].append(evaluator)
    for name, payload in [("portfolio-status", status), ("track-portfolio", portfolio)]:
        (evidence_root / f"artifacts/{name}.json").write_bytes(registry_api.canonical_bytes(payload))
    with pytest.raises(ValueError, match="missing or unsafe"):
        registry_api.validate_evidence(registry, evidence_root)
    acceptance = registry_api.load_json((evidence_root / "artifacts/t2-causal/acceptance.json").read_text())
    acceptance.update(track="T6", evaluator=evaluator)
    target = evidence_root / extension["acceptance"]
    target.parent.mkdir()
    target.write_bytes(registry_api.canonical_bytes(acceptance))
    result = registry_api.validate_evidence(registry, evidence_root)
    assert result["track_count"] == 6
    assert result["boundaries"]["scientific_validity"] is False


@pytest.mark.parametrize("mutation", ["identity", "typed-exit-code"])
def test_registry_row_is_separately_checked_without_hash_cycle(mutation: str, monkeypatch: pytest.MonkeyPatch) -> None:
    root = registry_api.load_json((verify_track_registry.ROOT / "artifacts/acceptance.json").read_text())
    original_projection = registry_api.acceptance_projection(root)
    row = next(item for item in root["checks"] if item["name"] == registry_api.REGISTRY_ROW)
    if mutation == "identity":
        row["input_version"] = "tampered"
    else:
        row["exit_code"] = False
    assert registry_api.acceptance_projection(root) == original_projection
    original_load = verify_track_registry._load
    monkeypatch.setattr(verify_track_registry, "_load", lambda path: root if path == verify_track_registry.ROOT / "artifacts/acceptance.json" else original_load(path))
    with pytest.raises(ValueError, match="root acceptance row differs"):
        verify_track_registry.verify_saved()


def test_duplicate_self_rows_are_rejected() -> None:
    root = registry_api.load_json((verify_track_registry.ROOT / "artifacts/acceptance.json").read_text())
    root["checks"].append(deepcopy(next(row for row in root["checks"] if row["name"] == registry_api.REGISTRY_ROW)))
    with pytest.raises(ValueError, match="duplicate or invalid acceptance"):
        registry_api.acceptance_projection(root)


@pytest.mark.parametrize("content", ['{"track_id":"T1","track_id":"T2"}', '{"value":NaN}'])
def test_ambiguous_json_is_rejected(content: str) -> None:
    with pytest.raises(ValueError):
        registry_api.load_json(content)


def test_module_cli_distinguishes_declaration_and_evidence() -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(verify_track_registry.ROOT / "src")
    declaration = subprocess.run([sys.executable, "-m", "auditable_scientist.track_registry"],
                                 capture_output=True, text=True, check=True, env=environment)
    result = json.loads(declaration.stdout)
    assert result["status"] == "valid-declaration-only"
    assert result["evidence_checked"] is False
