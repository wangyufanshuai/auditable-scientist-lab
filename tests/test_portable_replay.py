"""Portable v2 run packages must replay from a different checkout path."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from auditable_scientist.cli import main


ROOT = Path(__file__).resolve().parents[1]


def test_six_runs_replay_in_copied_checkout_without_original_fixtures(tmp_path: Path, capsys) -> None:
    generated: list[Path] = []
    assert main(["run", str(ROOT / "examples/hohmann/run.json"), "--offline", "--seed", "17", "--output-dir", str(tmp_path / "source-runs")]) == 0
    generated.append(Path(capsys.readouterr().out.strip()))
    for track_id, fixture in (
        ("T2", "examples/causal/fixture.json"),
        ("T3", "examples/dynamics/fixture.json"),
        ("T4", "examples/proof/fixture.json"),
        ("T4O", "examples/proof/oscillator-fixture.json"),
        ("T5", "examples/protocol/fixture.json"),
    ):
        assert main(["run-track", track_id, str(ROOT / fixture), "--output-dir", str(tmp_path / "source-tracks")]) == 0
        generated.append(Path(capsys.readouterr().out.strip()))
    moved = tmp_path / "moved-checkout"
    moved.mkdir()
    for directory in ("src", "docs", "schemas"):
        shutil.copytree(ROOT / directory, moved / directory, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (moved / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/generate_track_artifacts.py", moved / "scripts/generate_track_artifacts.py")
    shutil.copy2(ROOT / "pyproject.toml", moved / "pyproject.toml")
    runs = [f"{'t1' if index == 0 else 'tracks'}/{source.name}" for index, source in enumerate(generated)]
    for source, relative in zip(generated, runs, strict=True):
        destination = moved / "artifacts" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
    # The copied checkout intentionally has no top-level examples directory.
    assert not (moved / "examples").exists()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(moved / "src")
    script = (
        "from pathlib import Path\n"
        "import auditable_scientist\n"
        "from auditable_scientist.cli import main\n"
        "root=Path.cwd().resolve()\n"
        "assert Path(auditable_scientist.__file__).resolve().is_relative_to(root/'src')\n"
        f"runs={runs!r}\n"
        "for relative in runs:\n"
        "    assert main(['replay', str(root/'artifacts'/relative)]) == 0, relative\n"
        "fixture=root/'artifacts'/runs[2]/'fixture.json'\n"
        "fixture.write_text('tampered copied fixture', encoding='utf-8')\n"
        "assert main(['replay', str(root/'artifacts'/runs[2])]) == 2\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script], cwd=moved, env=environment,
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.count('"verified": true') == 6
    assert "error:" in completed.stderr
