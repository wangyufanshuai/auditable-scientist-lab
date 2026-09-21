"""Policy-enforced execution of registered tools.

The policy layer is intentionally small. It is an execution guard, not a scientific
judge: it can deny a tool call, but it cannot promote a Claim or decide whether an
observation is true.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any, Callable

from ..domain import Policy, Tool


class PolicyDenied(PermissionError):
    """Raised when a registered tool call violates the active policy."""


@dataclass(frozen=True)
class RegisteredTool:
    declaration: Tool
    handler: Callable[[dict[str, Any]], Any]


class ToolRegistry:
    """Register and invoke tools under network, path, provider, count, and time gates."""

    def __init__(self, policy: Policy):
        self.policy = policy
        self._tools: dict[str, RegisteredTool] = {}
        self._calls = 0
        self._started = monotonic()

    @property
    def calls_used(self) -> int:
        return self._calls

    def register(self, declaration: Tool, handler: Callable[[dict[str, Any]], Any]) -> None:
        if declaration.tool_id in self._tools:
            raise ValueError(f"tool already registered: {declaration.tool_id}")
        self._tools[declaration.tool_id] = RegisteredTool(declaration, handler)

    def invoke(
        self,
        tool_id: str,
        arguments: dict[str, Any],
        *,
        path_refs: list[str] | None = None,
        provider_id: str | None = None,
    ) -> Any:
        registered = self._tools.get(tool_id)
        if registered is None:
            raise PolicyDenied(f"tool is not registered: {tool_id}")
        if self._calls >= self.policy.max_tool_calls:
            raise PolicyDenied("tool-call budget exceeded")
        if monotonic() - self._started > self.policy.max_seconds:
            raise PolicyDenied("time budget exceeded")
        if registered.declaration.network_required and self.policy.network == "disabled":
            raise PolicyDenied(f"network-required tool denied by policy: {tool_id}")
        if provider_id is not None and provider_id not in self.policy.allowed_providers:
            raise PolicyDenied(f"provider is not allowlisted: {provider_id}")
        self._check_paths(path_refs or [])
        self._calls += 1
        return registered.handler(arguments)

    def _check_paths(self, path_refs: list[str]) -> None:
        if not path_refs:
            return
        if not self.policy.allowed_paths:
            raise PolicyDenied("path access denied because allowed_paths is empty")
        roots = [Path(item).resolve() for item in self.policy.allowed_paths]
        for raw_path in path_refs:
            candidate = Path(raw_path).resolve()
            if not any(_is_relative_to(candidate, root) for root in roots):
                raise PolicyDenied(f"path is outside policy scope: {raw_path}")


def _is_relative_to(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True
