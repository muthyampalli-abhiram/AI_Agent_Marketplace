from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent
from app.schemas import AgentRegisterRequest, AgentOut, AgentStatusUpdate

router = APIRouter(tags=["agents"])


@router.post("/agents", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def register_agent(payload: AgentRegisterRequest, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.name == payload.name).first()
    if agent:
        agent.domain = payload.domain
        agent.description = payload.description
        agent.capabilities = payload.capabilities
        agent.endpoint = payload.endpoint
        agent.cost_per_call = payload.cost_per_call
    else:
        agent = Agent(
            name=payload.name,
            domain=payload.domain,
            description=payload.description,
            capabilities=payload.capabilities,
            endpoint=payload.endpoint,
            cost_per_call=payload.cost_per_call,
        )
        db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/agents", response_model=List[AgentOut])
def list_agents(
    domain: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    query = db.query(Agent)
    if domain:
        query = query.filter(Agent.domain == domain)
    if status_filter:
        query = query.filter(Agent.status == status_filter)
    return query.all()


@router.get("/agents/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )
    return agent


@router.patch("/agents/{agent_id}/status", response_model=AgentOut)
def update_agent_status(
    agent_id: str, payload: AgentStatusUpdate, db: Session = Depends(get_db)
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )
    agent.status = payload.status
    db.commit()
    db.refresh(agent)
    return agent
