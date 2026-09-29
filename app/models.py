import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), index=True, nullable=False)
    description = Column(Text, nullable=True)
    capabilities = Column(JSON, nullable=True)
    endpoint = Column(String(255), default="internal", nullable=False)
    cost_per_call = Column(Float, default=0.0, nullable=False)
    avg_latency_ms = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), default="active", nullable=False)
    performance_score = Column(Float, default=0.7, nullable=False)
    total_tasks = Column(Integer, default=0, nullable=False)
    total_failures = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    team_memberships = relationship("TeamMembership", back_populates="agent")


class TaskRun(Base):
    __tablename__ = "task_runs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    request_text = Column(Text, nullable=False)
    required_capabilities = Column(JSON, nullable=True)
    status = Column(String(50), default="running", nullable=False)
    consensus_output = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)

    team_memberships = relationship("TeamMembership", back_populates="task_run")


class TeamMembership(Base):
    __tablename__ = "team_memberships"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    task_run_id = Column(String(36), ForeignKey("task_runs.id"), nullable=False)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    subtask = Column(Text, nullable=True)
    role = Column(String(50), default="contributor", nullable=False)
    replaced_agent_id = Column(String(36), nullable=True)
    result_summary = Column(Text, nullable=True)
    success = Column(Boolean, nullable=True)
    latency_ms = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    task_run = relationship("TaskRun", back_populates="team_memberships")
    agent = relationship("Agent", back_populates="team_memberships")
