"""Read-only adapter boundaries and provider contracts.

Adapters describe external sources and contracts. They do not copy or import code from
the inventoried projects unless a separate license and revision gate is closed.
"""

from .manifests import AdapterManifest, AdapterStatus, built_in_manifests
from .providers import (
    AdapterBlocked,
    BlockedExternalSymbolicProvider,
    SymbolicCandidate,
    SymbolicProviderRequest,
    SymbolicProviderResult,
)
from .evidence import EvidenceReference, map_external_evidence
from .project05 import Project05Adapter, Project05File, Project05Snapshot

__all__ = [
    "AdapterBlocked",
    "AdapterManifest",
    "AdapterStatus",
    "BlockedExternalSymbolicProvider",
    "EvidenceReference",
    "Project05Adapter",
    "Project05File",
    "Project05Snapshot",
    "SymbolicCandidate",
    "SymbolicProviderRequest",
    "SymbolicProviderResult",
    "built_in_manifests",
    "map_external_evidence",
]
