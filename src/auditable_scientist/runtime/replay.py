"""Replay manifest creation and fail-closed verification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field

from ..domain import StrictModel
from .canonical import canonical_hash


class ReplayMismatch(ValueError):
    """Raised when the current state cannot reproduce a registered manifest."""


class BoundPaths:
    """Stable file references constrained to one run and its installation root."""

    def __init__(self, *, root: Path, run_dir: Path) -> None:
        self.root = root.resolve()
        self.run_dir = run_dir.resolve()

    def ref(self, path: str | Path) -> str:
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise ReplayMismatch(f"registered file is missing: {resolved}")
        for scheme, base in (("run", self.run_dir), ("root", self.root)):
            if resolved.is_relative_to(base):
                return f"{scheme}://{resolved.relative_to(base).as_posix()}"
        raise ReplayMismatch(f"file is outside the registered run and root: {resolved}")

    def resolve(self, reference: str) -> Path:
        scheme, separator, relative = reference.partition("://")
        if not separator or scheme not in ("run", "root"):
            raise ReplayMismatch("file reference has an unsupported scheme")
        if not relative or "\\" in relative or any(part in ("", ".", "..") or ":" in part for part in relative.split("/")):
            raise ReplayMismatch("file reference has an unsafe relative path")
        base = self.run_dir if scheme == "run" else self.root
        resolved = (base / relative).resolve()
        if not resolved.is_relative_to(base) or not resolved.is_file():
            raise ReplayMismatch("file reference escapes its root or is missing")
        return resolved

    def fingerprint(self, path: str | Path) -> "FileFingerprint":
        actual = fingerprint_file(path)
        return actual.model_copy(update={"path": self.ref(path)})


class FileFingerprint(StrictModel):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bytes: int = Field(ge=0)


class ReplayReceipt(StrictModel):
    verified: bool
    checks: list[str]
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ReplayManifest(StrictModel):
    schema_version: str = "replay-manifest-v1"
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    code_revision: str = Field(min_length=1)
    environment: dict[str, Any]
    seed: int = Field(ge=0)
    source_files: list[FileFingerprint] = Field(default_factory=list)
    evidence_files: list[FileFingerprint] = Field(default_factory=list)
    candidate_order: list[str] = Field(default_factory=list)
    computational_output: Any

    @classmethod
    def create(
        cls,
        *,
        input_payload: Any,
        code_revision: str,
        environment: dict[str, Any],
        seed: int,
        source_paths: list[str | Path] | None = None,
        evidence_paths: list[str | Path] | None = None,
        candidate_order: list[str] | None = None,
        computational_output: Any,
        bindings: BoundPaths | None = None,
    ) -> "ReplayManifest":
        return cls(
            schema_version="replay-manifest-v2" if bindings is not None else "replay-manifest-v1",
            input_hash=canonical_hash(input_payload),
            code_revision=code_revision,
            environment=environment,
            seed=seed,
            source_files=[(bindings.fingerprint(path) if bindings else fingerprint_file(path)) for path in (source_paths or [])],
            evidence_files=[(bindings.fingerprint(path) if bindings else fingerprint_file(path)) for path in (evidence_paths or [])],
            candidate_order=list(candidate_order or []),
            computational_output=computational_output,
        )

    def write(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.model_dump_json(indent=2), encoding="utf-8", newline="\n")
        return destination

    @classmethod
    def load(cls, path: str | Path) -> "ReplayManifest":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def verify(
        self,
        *,
        input_payload: Any | None = None,
        code_revision: str | None = None,
        environment: dict[str, Any] | None = None,
        seed: int | None = None,
        source_paths: list[str | Path] | None = None,
        evidence_paths: list[str | Path] | None = None,
        candidate_order: list[str] | None = None,
        computational_output: Any | None = None,
        bindings: BoundPaths | None = None,
    ) -> ReplayReceipt:
        checks: list[str] = []
        if self.schema_version not in ("replay-manifest-v1", "replay-manifest-v2"):
            raise ReplayMismatch("replay manifest version is unsupported")
        if self.schema_version == "replay-manifest-v2" and bindings is None:
            raise ReplayMismatch("portable replay manifest requires bound paths")
        if input_payload is not None:
            assert_hash("input", self.input_hash, canonical_hash(input_payload))
            checks.append("input_hash")
        if code_revision is not None:
            if code_revision != self.code_revision:
                raise ReplayMismatch("code revision changed")
            checks.append("code_revision")
        if environment is not None:
            if canonical_hash(environment) != canonical_hash(self.environment):
                raise ReplayMismatch("runtime environment changed")
            checks.append("environment")
        if seed is not None:
            if seed != self.seed:
                raise ReplayMismatch("random seed changed")
            checks.append("seed")
        verify_files("source", self.source_files, source_paths, bindings=bindings if self.schema_version == "replay-manifest-v2" else None)
        if source_paths is not None:
            checks.append("source_files")
        verify_files("evidence", self.evidence_files, evidence_paths, bindings=bindings if self.schema_version == "replay-manifest-v2" else None)
        if evidence_paths is not None:
            checks.append("evidence_files")
        if candidate_order is not None:
            if list(candidate_order) != self.candidate_order:
                raise ReplayMismatch("candidate ordering changed")
            checks.append("candidate_order")
        if computational_output is not None:
            if canonical_hash(computational_output) != canonical_hash(self.computational_output):
                raise ReplayMismatch("computational output changed")
            checks.append("computational_output")
        return ReplayReceipt(verified=True, checks=checks, manifest_hash=canonical_hash(self))


def fingerprint_file(path: str | Path) -> FileFingerprint:
    file_path = Path(path)
    if not file_path.is_file():
        raise ReplayMismatch(f"registered file is missing: {file_path}")
    return FileFingerprint(path=str(path), sha256=sha256_file(file_path), bytes=file_path.stat().st_size)


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_hash(label: str, expected: str, actual: str) -> None:
    if expected != actual:
        raise ReplayMismatch(f"{label} hash changed")


def verify_files(label: str, expected: list[FileFingerprint], paths: list[str | Path] | None, *, bindings: BoundPaths | None = None) -> None:
    if paths is None:
        return
    actual = [(bindings.fingerprint(path) if bindings else fingerprint_file(path)) for path in paths]
    if actual != expected:
        raise ReplayMismatch(f"{label} file snapshot changed")
