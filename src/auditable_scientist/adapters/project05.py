"""Read-only source snapshot adapter for the selected project-05 benchmark."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..runtime.replay import fingerprint_file
from .manifests import AdapterManifest, AdapterStatus


class Project05File(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bytes: int = Field(ge=0)


class Project05Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str = "project-05-hohmann-v1"
    source_path: str = Field(min_length=1)
    status: Literal["verified", "unverified", "blocked"]
    license_status: str = Field(min_length=1)
    files: list[Project05File] = Field(default_factory=list)
    notes: str = ""


class Project05Adapter:
    """Describe the source without importing or copying its implementation."""

    required_files = (
        "README.md",
        "references.md",
        "src/main.py",
        "data/mars_hohmann_summary.csv",
    )

    def __init__(self, root: str | Path = r"E:\xuexi\projects\05_hohmann_mars_transfer"):
        self.root = Path(root)

    @property
    def manifest(self) -> AdapterManifest:
        return AdapterManifest(
            adapter_id="project-05-hohmann",
            kind="benchmark-source",
            status=AdapterStatus.UNVERIFIED,
            source_path_or_uri=str(self.root),
            source_revision="local-snapshot",
            license_status="no root LICENSE confirmed",
            capabilities=["read-baseline-description", "read-reference-data"],
            notes="Read-only snapshot; the target package keeps an independent fixture and does not copy source code.",
        )

    def snapshot(self) -> Project05Snapshot:
        if not self.root.is_dir():
            return Project05Snapshot(
                source_path=str(self.root),
                status="blocked",
                license_status="unknown",
                notes="source directory is missing; external adapter remains blocked",
            )
        files: list[Project05File] = []
        missing: list[str] = []
        for relative in self.required_files:
            path = self.root / relative
            if not path.is_file():
                missing.append(relative)
                continue
            fingerprint = fingerprint_file(path)
            files.append(Project05File(relative_path=relative, sha256=fingerprint.sha256, bytes=fingerprint.bytes))
        status = "unverified" if not missing else "blocked"
        return Project05Snapshot(
            source_path=str(self.root),
            status=status,
            license_status="no root LICENSE confirmed",
            files=files,
            notes=("all selected source files are present; source remains read-only" if not missing else f"missing files: {missing}"),
        )

    def verify_snapshot(self, snapshot: Project05Snapshot, *, allow_missing_source: bool = False) -> bool:
        """Verify a snapshot against the source, or its committed shape offline.

        A clean checkout does not contain the user's external project-05 source
        directory.  In that environment the committed snapshot can still be
        checked as a static provenance record, while a checkout that does have
        the source continues to require byte-for-byte verification.
        """
        if snapshot.status == "blocked":
            return False
        if not self.root.is_dir():
            return allow_missing_source and self._is_complete_static_snapshot(snapshot)
        current = self.snapshot()
        return current.status == snapshot.status and current.files == snapshot.files

    def _is_complete_static_snapshot(self, snapshot: Project05Snapshot) -> bool:
        relative_paths = [item.relative_path for item in snapshot.files]
        return (
            snapshot.status == "unverified"
            and snapshot.license_status == "no root LICENSE confirmed"
            and len(relative_paths) == len(set(relative_paths))
            and set(relative_paths) == set(self.required_files)
        )
