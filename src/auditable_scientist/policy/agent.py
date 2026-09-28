"""Offline agent proposals that cannot promote scientific claims."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..domain import Agent
from .runtime import ToolRegistry


class AgentProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(min_length=1)
    proposal_type: Literal["question", "hypothesis", "explanation"]
    content: str = Field(min_length=1)
    requested_tool_ids: list[str] = Field(default_factory=list)


class OfflineAgent:
    """A deterministic propositional agent; evaluator and claims stay outside its authority."""

    def __init__(self, declaration: Agent, registry: ToolRegistry):
        self.declaration = declaration
        self.registry = registry

    def propose(self, *, proposal_id: str, proposal_type: str, content: str, requested_tool_ids: list[str] | None = None) -> AgentProposal:
        return AgentProposal(
            proposal_id=proposal_id,
            proposal_type=proposal_type,
            content=content,
            requested_tool_ids=list(requested_tool_ids or []),
        )

    def invoke_registered_tool(self, tool_id: str, arguments: dict[str, object]) -> object:
        return self.registry.invoke(tool_id, arguments)
