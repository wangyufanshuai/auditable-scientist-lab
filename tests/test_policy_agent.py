from __future__ import annotations

from pathlib import Path

import pytest

from auditable_scientist.domain import Agent, Policy, Tool
from auditable_scientist.policy import AgentProposal, OfflineAgent, PolicyDenied, ToolRegistry


def _tool(*, tool_id: str = "echo", network_required: bool = False) -> Tool:
    return Tool(
        tool_id=tool_id,
        name=tool_id,
        version="1",
        parameter_schema_ref="schemas/echo.json",
        deterministic=True,
        network_required=network_required,
    )


def test_offline_agent_can_propose_and_call_registered_tool() -> None:
    registry = ToolRegistry(
        Policy(policy_id="offline", network="disabled", max_seconds=5, max_tool_calls=1, allowed_paths=[])
    )
    registry.register(_tool(), lambda arguments: {"echo": arguments["value"]})
    agent = OfflineAgent(Agent(agent_id="a1", name="offline", version="1"), registry)
    proposal = agent.propose(proposal_id="p1", proposal_type="hypothesis", content="candidate", requested_tool_ids=["echo"])
    assert isinstance(proposal, AgentProposal)
    assert agent.invoke_registered_tool("echo", {"value": 3}) == {"echo": 3}
    assert registry.calls_used == 1


def test_policy_denies_network_tool_and_unknown_provider() -> None:
    registry = ToolRegistry(
        Policy(policy_id="offline", network="disabled", max_seconds=5, max_tool_calls=3, allowed_paths=[], allowed_providers=["local"])
    )
    registry.register(_tool(tool_id="remote", network_required=True), lambda _: "unreachable")
    with pytest.raises(PolicyDenied, match="network-required"):
        registry.invoke("remote", {})
    registry.register(_tool(tool_id="local"), lambda _: "ok")
    with pytest.raises(PolicyDenied, match="not allowlisted"):
        registry.invoke("local", {}, provider_id="external")


def test_policy_denies_path_outside_allowlist_and_call_budget() -> None:
    allowed = Path.cwd() / "examples"
    registry = ToolRegistry(
        Policy(policy_id="scoped", network="disabled", max_seconds=5, max_tool_calls=1, allowed_paths=[str(allowed)])
    )
    registry.register(_tool(), lambda _: "ok")
    assert registry.invoke("echo", {}, path_refs=[str(allowed / "hohmann")]) == "ok"
    path_registry = ToolRegistry(
        Policy(policy_id="path-only", network="disabled", max_seconds=5, max_tool_calls=1, allowed_paths=[str(allowed)])
    )
    path_registry.register(_tool(), lambda _: "ok")
    with pytest.raises(PolicyDenied, match="outside policy scope"):
        path_registry.invoke("echo", {}, path_refs=[str(Path.cwd().parent)])
    with pytest.raises(PolicyDenied, match="budget"):
        registry.invoke("echo", {})


def test_registered_tool_arguments_are_schema_checked() -> None:
    registry = ToolRegistry(Policy(policy_id="offline", network="disabled", max_seconds=5, max_tool_calls=3))
    registry.register(
        _tool(),
        lambda arguments: arguments["value"],
        argument_schema={
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    with pytest.raises(PolicyDenied, match="missing required"):
        registry.invoke("echo", {})
    with pytest.raises(PolicyDenied, match="invalid type"):
        registry.invoke("echo", {"value": "1"})
    assert registry.invoke("echo", {"value": 1}) == 1


def test_registered_tool_enforces_enum_and_hash_pattern() -> None:
    registry = ToolRegistry(Policy(policy_id="offline", network="disabled", max_seconds=5, max_tool_calls=1))
    registry.register(
        _tool(),
        lambda arguments: arguments,
        argument_schema={
            "type": "object",
            "required": ["track_id", "input_hash"],
            "properties": {
                "track_id": {"enum": ["T2"]},
                "input_hash": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            },
            "additionalProperties": False,
        },
    )
    with pytest.raises(PolicyDenied, match="violate schema"):
        registry.invoke("echo", {"track_id": "T3", "input_hash": "0" * 64})
    with pytest.raises(PolicyDenied, match="violate schema"):
        registry.invoke("echo", {"track_id": "T2", "input_hash": "bad"})
    assert registry.calls_used == 0


def test_agent_proposal_cannot_encode_a_claim_transition() -> None:
    registry = ToolRegistry(Policy(policy_id="offline", network="disabled", max_seconds=5, max_tool_calls=0))
    agent = OfflineAgent(Agent(agent_id="a1", name="offline", version="1"), registry)
    proposal = agent.propose(proposal_id="p1", proposal_type="explanation", content="bounded")
    assert "status" not in proposal.model_dump()
    with pytest.raises(ValueError):
        AgentProposal.model_validate({**proposal.model_dump(), "status": "reproduced"})
