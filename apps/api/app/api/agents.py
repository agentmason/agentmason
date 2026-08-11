from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.core.security import decode_access_token
from apps.api.app.models.execution import AgentExecution
from apps.api.app.models.membership import Membership
from apps.api.app.models.user import User
from packages.agents.business_assistant import BusinessAssistantAgent
from packages.agents.engine import AgentExecutionEngine
from packages.agents.registry import AgentRegistry
from packages.llm.config import ProviderConfig
from packages.llm.factory import LLMProviderFactory
from packages.tools.calculator import CalculatorTool
from packages.tools.datetime_tool import DateTimeTool
from packages.tools.registry import ToolRegistry
from packages.tools.text_analysis import TextAnalysisTool

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class AgentRunRequest(BaseModel):
    agent_name: str
    input: str
    organization_id: Optional[str] = None


class AgentResponse(BaseModel):
    execution_id: str
    status: str
    output: Optional[dict[str, Any]] = None
    trace: list[dict[str, Any]]


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        claims = decode_access_token(token)
        user_id = str(claims.get("sub"))
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials") from exc

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.post("/run", response_model=AgentResponse)
async def run_agent(payload: AgentRunRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> AgentResponse:
    organization_id = payload.organization_id
    if not organization_id:
        membership = db.scalar(select(Membership).where(Membership.user_id == current_user.id).limit(1))
        organization_id = str(membership.organization_id) if membership else str(current_user.id)

    config = ProviderConfig(
        provider="local",
        model="local-model",
    )
    llm_provider = LLMProviderFactory.create("local", config)
    tool_registry = ToolRegistry()
    tool_registry.register(CalculatorTool())
    tool_registry.register(DateTimeTool())
    tool_registry.register(TextAnalysisTool())

    registry = AgentRegistry()
    registry.register(BusinessAssistantAgent(tools=tool_registry.list()))
    try:
        agent = registry.get(payload.agent_name)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    executor = AgentExecutionEngine(tool_registry=tool_registry, llm_provider=llm_provider)
    result = await executor.run(agent, payload.input)

    execution = AgentExecution(
        id=result["execution_id"],
        organization_id=organization_id,
        user_id=str(current_user.id),
        agent_name=payload.agent_name,
        status=result["status"],
        input={"input": payload.input},
        output=result.get("output"),
        error=None,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    return AgentResponse(
        execution_id=execution.id,
        status=execution.status,
        output=execution.output,
        trace=result["trace"],
    )


@router.post("/stream")
async def stream_agent(payload: AgentRunRequest, current_user: User = Depends(get_current_user)) -> StreamingResponse:
    config = ProviderConfig(provider="local", model="local-model")
    llm_provider = LLMProviderFactory.create("local", config)
    messages = [
        {"role": "system", "content": "You are AgentMason, a business assistant."},
        {"role": "user", "content": payload.input},
    ]

    async def event_generator() -> Any:
        execution_id = str(uuid4())
        yield f"event: execution_started\ndata: {execution_id}\n\n"
        try:
            async for event in llm_provider.stream(messages):
                if event.get("type") == "token":
                    yield f"event: token\ndata: {event['text']}\n\n"
            yield "event: execution_completed\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {str(exc)}\n\n"
            yield "event: execution_failed\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
