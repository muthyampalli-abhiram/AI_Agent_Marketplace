from typing import Any, Dict, List, Optional, TypedDict


class SubtaskAssignment(TypedDict):
    domain: str
    capability: str
    subtask: str
    agent_id: Optional[str]
    agent_name: Optional[str]
    result: Optional[str]
    success: Optional[bool]
    latency_ms: Optional[float]
    retries: int


class OrchestratorState(TypedDict):
    task_run_id: str
    request_text: str
    context: Dict[str, Any]
    required: List[Dict[str, Any]]
    assignments: List[SubtaskAssignment]
    unfilled: List[Dict[str, Any]]
    completed: List[SubtaskAssignment]
    failed: List[SubtaskAssignment]
    consensus_output: Optional[str]
    status: str
