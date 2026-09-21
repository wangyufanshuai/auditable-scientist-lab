"""Explicit provenance manifests for local and external adapter boundaries."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AdapterStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    BLOCKED = "blocked"


class AdapterManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    status: AdapterStatus
    source_path_or_uri: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    license_status: str = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    read_only: bool = True
    code_reuse_allowed: bool = False
    notes: str = ""


def built_in_manifests() -> list[AdapterManifest]:
    """Return the inventory-derived manifests without touching external worktrees."""

    return [
        AdapterManifest(
            adapter_id="project-05-hohmann",
            kind="benchmark-source",
            status=AdapterStatus.UNVERIFIED,
            source_path_or_uri="E:/xuexi/projects/05_hohmann_mars_transfer",
            source_revision="local-snapshot-2026-09-20",
            license_status="no root LICENSE confirmed",
            capabilities=["read-baseline-description", "read-reference-data"],
            notes="The P4 fixture is committed independently; source worktree remains read-only.",
        ),
        AdapterManifest(
            adapter_id="engineering-research-copilot",
            kind="tool-contract",
            status=AdapterStatus.UNVERIFIED,
            source_path_or_uri="E:/xuexi/engineering-research-copilot",
            source_revision="local-snapshot-2026-09-20",
            license_status="no root LICENSE confirmed",
            capabilities=["tool-schema-reference"],
            notes="Contract-level reference only; no source code is imported or copied.",
        ),
        AdapterManifest(
            adapter_id="paper2project",
            kind="evidence-contract",
            status=AdapterStatus.UNVERIFIED,
            source_path_or_uri="E:/xuexi/paper2project",
            source_revision="local-snapshot-2026-09-20",
            license_status="no root LICENSE confirmed",
            capabilities=["evidence-id-mapping"],
            notes="Evidence IDs may be mapped after provenance checks; source code is not reused.",
        ),
        AdapterManifest(
            adapter_id="physics-programmable-learning",
            kind="policy-reference",
            status=AdapterStatus.UNVERIFIED,
            source_path_or_uri="E:/xuexi/physics-programmable-learning",
            source_revision="dirty-worktree-read-only",
            license_status="MIT-confirmed",
            capabilities=["evidence-policy-reference", "release-gate-reference"],
            notes="MIT license is recorded, but this adapter remains a read-only policy reference.",
        ),
        AdapterManifest(
            adapter_id="symbolic-physics-engine",
            kind="symbolic-provider",
            status=AdapterStatus.BLOCKED,
            source_path_or_uri="E:/xuexi/symbolic-physics-engine",
            source_revision="missing",
            license_status="unknown",
            capabilities=["symbolic-candidate-generation"],
            notes="Blocked until a real path or repository, revision, and license are supplied.",
        ),
    ]
