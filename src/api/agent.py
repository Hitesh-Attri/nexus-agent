"""POST /agent - run the reason -> act -> observe loop over a task."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.agent import run_agent
from core.gateway import GatewayError

router = APIRouter()


class AgentRequest(BaseModel):
    task: str = Field(min_length=1)
    max_iterations: int | None = Field(default=None, ge=1, le=20)


class StepModel(BaseModel):
    n: int
    thought: str
    action: str
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    observation: str | None = None
    answer: str | None = None
    error: str | None = None


class AgentResponse(BaseModel):
    task: str
    answer: str
    iterations: int
    stopped: str
    steps: list[StepModel]


@router.post("/agent", response_model=AgentResponse)
def run(body: AgentRequest) -> AgentResponse:
    try:
        result = run_agent(body.task, body.max_iterations)
    except GatewayError as e:
        # The gateway being unreachable is an infrastructure failure, not
        # something the loop can reason around.
        raise HTTPException(status_code=503, detail=f"gateway unavailable: {e}") from e
    return AgentResponse(task=body.task, **result)