from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class AgentRegisterRequest(BaseModel):
    name: str
    domain: str
    description: Optional[str] = None
    capabilities: List[str] = []
    endpoint: str = "internal"
    cost_per_call: float = 0.0


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    domain: str
    description: Optional[str] = None
    capabilities: Optional[List[str]] = None
    status: str
    performance_score: float
    total_tasks: int
    total_failures: int


class AgentStatusUpdate(BaseModel):
    status: str


class AnalyzeRequest(BaseModel):
    request_text: str
    context: Optional[dict] = None


class AnalyzeResponse(BaseModel):
    task_run_id: str
    team: List[dict]
    consensus_output: str
    status: str
    analytics_url: str
