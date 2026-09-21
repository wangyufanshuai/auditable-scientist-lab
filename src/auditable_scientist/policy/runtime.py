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
    argument_schema: dict[str, Any] | None = None


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

    def register(
        self,
        declaration: Tool,
        handler: Callable[[dict[str, Any]], Any],
        *,
        argument_schema: dict[str, Any] | None = None,
    ) -> None:
        if declaration.tool_id in self._tools:
            raise ValueError(f"tool already registered: {declaration.tool_id}")
        self._tools[declaration.tool_id] = RegisteredTool(declaration, handler, argument_schema)

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
        self._validate_arguments(registered.argument_schema, arguments)
        self._calls += 1
        return registered.handler(arguments)

    @staticmethod
    def _validate_arguments(schema: dict[str, Any] | None, arguments: dict[str, Any]) -> None:
        if schema is None:
            return
        if schema.get("type", "object") != "object":
            raise PolicyDenied("tool argument schema must describe an object")
        required = schema.get("required", [])
        missing = [name for name in required if name not in arguments]
        if missing:
            raise PolicyDenied(f"tool arguments missing required fields: {missing}")
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(arguments) - set(schema.get("properties", {})))
            if unknown:
                raise PolicyDenied(f"tool arguments contain unknown fields: {unknown}")
        for name, declaration in schema.get("properties", {}).items():
            if name not in arguments:
                continue
            expected = declaration.get("type")
            value = arguments[name]
            valid = {
                "string": isinstance(value, str),
                "number": isinstance(value, (int, float)) and not isinstance(value, bool),
                "integer": isinstance(value, int) and not isinstance(value, bool),
                "boolean": isinstance(value, bool),
                "array": isinstance(value, list),
                "object": isinstance(value, dict),
            }.get(expected, True)
            if not valid:
                raise PolicyDenied(f"tool argument has invalid type: {name}")

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
