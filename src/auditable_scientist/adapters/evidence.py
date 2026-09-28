"""Contract-level evidence-ID mapping for read-only external references."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    provenance_status: str = Field(pattern=r"^(verified|unverified|blocked)$")
    allowed_use: list[str] = Field(min_length=1)
    notes: str = ""


def map_external_evidence(
    *, evidence_id: str, adapter_id: str, external_id: str, source_revision: str, provenance_status: str, allowed_use: list[str]
) -> EvidenceReference:
    """Create a mapping record without resolving or copying the external artifact."""

    return EvidenceReference(
        evidence_id=evidence_id,
        adapter_id=adapter_id,
        external_id=external_id,
        source_revision=source_revision,
        provenance_status=provenance_status,
        allowed_use=allowed_use,
    )
