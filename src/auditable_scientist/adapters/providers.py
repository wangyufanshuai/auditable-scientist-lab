"""Provider protocol with an explicit blocked external implementation."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from .manifests import AdapterManifest, AdapterStatus


class AdapterBlocked(RuntimeError):
    """Raised when a provider has not passed its source and license gate."""


class SymbolicProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    variables: list[str] = Field(min_length=1)
    units: dict[str, str]
    target: str = Field(min_length=1)
    candidate_budget: int = Field(ge=1)
    seed: int = Field(ge=0)


class SymbolicCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str = Field(min_length=1)
    source_provider: str = Field(min_length=1)
    provider_revision: str = Field(min_length=1)
    candidate_rank: int = Field(ge=0)


class SymbolicProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(min_length=1)
    candidates: list[SymbolicCandidate]
    blocked: bool = False
    notes: str = ""


class SymbolicProvider(Protocol):
    manifest: AdapterManifest

    def generate(self, request: SymbolicProviderRequest) -> SymbolicProviderResult:
        ...


class BlockedExternalSymbolicProvider:
    """Protocol-compatible provider that fails closed until provenance is resolved."""

    def __init__(self, manifest: AdapterManifest):
        if manifest.status is not AdapterStatus.BLOCKED:
            raise ValueError("blocked provider requires a blocked adapter manifest")
        self.manifest = manifest

    def generate(self, request: SymbolicProviderRequest) -> SymbolicProviderResult:
        raise AdapterBlocked(
            f"provider {self.manifest.adapter_id} is blocked: "
            f"{self.manifest.notes or 'source and license gate is open'}"
        )
