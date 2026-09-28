"""Offline CLI router for current and historically source-bound Runs."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

from . import cli as legacy_cli
from . import cli_v2
from .runtime.paths import resource_path
from .runtime.replay import ReplayMismatch, fingerprint_file


BUNDLE = Path(__file__).resolve().parent / "_resources/legacy-runtime-8c26a26.zip"
BUNDLE_SHA256 = "537b63d3d617dbfcf1cd99f85ee8d79c8919d08fbdd4be272f4814c789c7c93b"


def _bundle_manifest() -> dict:
    if fingerprint_file(BUNDLE).sha256 != BUNDLE_SHA256:
        raise ReplayMismatch("pinned historical runtime bundle changed")
    with ZipFile(BUNDLE) as archive:
        if archive.namelist().count("legacy-runtime.json") != 1:
            raise ReplayMismatch("historical runtime inventory is missing")
        manifest = json.loads(archive.read("legacy-runtime.json"))
        if manifest.get("schema_version") != "legacy-runtime-bundle-v1":
            raise ReplayMismatch("unsupported historical runtime bundle")
        if set(archive.namelist()) != set(manifest["files"]) | {"legacy-runtime.json"}:
            raise ReplayMismatch("historical runtime file inventory changed")
        return manifest


def historical_source_matches(path: str, sha256_hex: str, byte_count: int) -> bool:
    """Verify an older acceptance source against the pinned original Git bytes."""

    manifest = _bundle_manifest()
    if manifest["files"].get(path) != sha256_hex:
        return False
    with ZipFile(BUNDLE) as archive:
        content = archive.read(path)
    return len(content) == byte_count and sha256(content).hexdigest() == sha256_hex


def _version(run_dir: Path) -> str:
    manifest = json.loads((run_dir / "replay-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "replay-manifest-v2":
        raise ReplayMismatch("unsupported Run replay manifest")
    sources = manifest.get("source_files")
    if not isinstance(sources, list):
        raise ReplayMismatch("Run source inventory is missing")
    if any(not isinstance(item, dict) or not isinstance(item.get("path"), str)
           or not isinstance(item.get("sha256"), str) for item in sources):
        raise ReplayMismatch("Run source inventory is malformed")
    by_path = {item["path"]: item["sha256"] for item in sources}
    if len(by_path) != len(sources):
        raise ReplayMismatch("duplicate Run source path")
    bundle = _bundle_manifest()
    old_project = bundle["files"]["pyproject.toml"]
    old_main = bundle["files"]["src/auditable_scientist/__main__.py"]
    current_project = fingerprint_file(resource_path("pyproject.toml")).sha256
    current_main = fingerprint_file(Path(__file__).resolve().parent / "__main__.py").sha256
    project = by_path.get("root://pyproject.toml") or by_path.get("root://_resources/pyproject.toml")
    main = by_path.get("root://src/auditable_scientist/__main__.py") or by_path.get("root://__main__.py")
    if project == old_project:
        return "historical-cli"
    if main == old_main:
        return "historical-v2"
    if project == current_project:
        return "current-cli"
    if main == current_main:
        return "current-v2"
    raise ReplayMismatch("Run has an unknown or changed CLI source version")


def _extract_bundle(root: Path, *, installed_layout: bool) -> None:
    manifest = _bundle_manifest()
    with ZipFile(BUNDLE) as archive:
        for name, expected_sha in manifest["files"].items():
            relative = Path(name)
            if (relative.is_absolute() or "\\" in name or
                    any(part in ("", ".", "..") for part in relative.parts)):
                raise ReplayMismatch("unsafe historical runtime path")
            content = archive.read(name)
            if sha256(content).hexdigest() != expected_sha:
                raise ReplayMismatch(f"historical runtime source changed: {name}")
            if installed_layout:
                prefix = "src/auditable_scientist/"
                if not name.startswith(prefix):
                    continue
                target = root / "site/auditable_scientist" / name[len(prefix):]
            else:
                target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)


def _copy_run(run_dir: Path, destination: Path) -> Path:
    if not run_dir.is_dir() or run_dir.is_symlink():
        raise ReplayMismatch("Run directory is missing or linked")
    for path in run_dir.rglob("*"):
        if path.is_symlink():
            raise ReplayMismatch("Run contains a linked file")
    copy = destination / run_dir.name
    shutil.copytree(run_dir, copy)
    return copy


def _historical_action(run_dir: Path, command: str) -> str:
    with tempfile.TemporaryDirectory(prefix="scientist-legacy-replay-") as temporary:
        root = Path(temporary).resolve()
        manifest = json.loads((run_dir / "replay-manifest.json").read_text(encoding="utf-8"))
        paths = {item["path"] for item in manifest["source_files"]}
        installed_layout = ("root://__main__.py" in paths or
                            "root://_resources/pyproject.toml" in paths)
        _extract_bundle(root, installed_layout=installed_layout)
        copied = _copy_run(run_dir, root / "runs")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(root / ("site" if installed_layout else "src"))
        module = "auditable_scientist" if _version(run_dir) == "historical-v2" else "auditable_scientist.cli"
        replay = subprocess.run(
            [sys.executable, "-m", module, "replay", str(copied)],
            cwd=root, env=environment, capture_output=True, text=True, timeout=120,
            check=False,
        )
        if replay.returncode != 0:
            raise ReplayMismatch(f"historical replay failed: {replay.stderr.strip()}")
        receipt = json.loads(replay.stdout)
        if receipt.get("verified") is not True:
            raise ReplayMismatch("historical replay did not verify")
        original_report = run_dir / "report.md"
        copied_report = copied / "report.md"
        if original_report.read_bytes() != copied_report.read_bytes():
            raise ReplayMismatch("historical report differs from deterministic replay")
        if command == "replay":
            return replay.stdout.strip()
        inspect = subprocess.run(
            [sys.executable, "-m", module, "inspect", str(copied)],
            cwd=root, env=environment, capture_output=True, text=True, timeout=120,
            check=False,
        )
        if inspect.returncode != 0:
            raise ReplayMismatch(f"historical inspect failed: {inspect.stderr.strip()}")
        return inspect.stdout.strip()


def _current_cli_action(run_dir: Path, command: str) -> str:
    with tempfile.TemporaryDirectory(prefix="scientist-current-replay-") as temporary:
        copied = _copy_run(run_dir, Path(temporary))
        output = StringIO()
        with redirect_stdout(output):
            if legacy_cli.main(["replay", str(copied)]) != 0:
                raise ReplayMismatch("current legacy CLI replay failed")
        receipt = json.loads(output.getvalue())
        if receipt.get("verified") is not True:
            raise ReplayMismatch("current legacy CLI replay did not verify")
        if (run_dir / "report.md").read_bytes() != (copied / "report.md").read_bytes():
            raise ReplayMismatch("current legacy report differs from replay")
        if command == "replay":
            return output.getvalue().strip()
        with redirect_stdout(output := StringIO()):
            if legacy_cli.main(["inspect", str(copied)]) != 0:
                raise ReplayMismatch("current legacy CLI inspect failed")
        return output.getvalue().strip()


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] not in ("replay", "inspect", "export-report"):
        return cli_v2.main(arguments)
    parser = argparse.ArgumentParser(prog="auditable-scientist")
    parser.add_argument("command", choices=("replay", "inspect", "export-report"))
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(arguments)
    if args.output is not None and args.command != "export-report":
        parser.error("--output is only valid with export-report")
    try:
        run_dir = args.run_dir.resolve()
        version = _version(run_dir)
        if version in ("historical-cli", "historical-v2"):
            output = _historical_action(run_dir, "replay" if args.command == "export-report" else args.command)
        elif version == "current-cli":
            output = _current_cli_action(run_dir, "replay" if args.command == "export-report" else args.command)
        else:
            return cli_v2.main(arguments)
        if args.command == "export-report":
            source = run_dir / "report.md"
            destination = args.output or source
            if destination.resolve() != source.resolve():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            print(destination)
        else:
            print(output)
        return 0
    except (FileNotFoundError, ValueError, OSError, PermissionError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def replay_verified_run(run_dir: Path) -> dict:
    """Return a version-routed receipt to acceptance verifiers."""

    output = StringIO()
    error = StringIO()
    with redirect_stdout(output), redirect_stderr(error):
        if main(["replay", str(run_dir)]) != 0:
            raise ReplayMismatch(f"versioned replay failed: {run_dir}: {error.getvalue().strip()}")
    receipt = json.loads(output.getvalue())
    if receipt.get("verified") is not True:
        raise ReplayMismatch(f"versioned replay did not verify: {run_dir}")
    return receipt


if __name__ == "__main__":
    raise SystemExit(main())
