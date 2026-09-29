from app.orchestrator.state import OrchestratorState, SubtaskAssignment

sample_assignment: SubtaskAssignment = {
    "domain": "finance", "capability": "finance", "subtask": "value the target",
    "agent_id": "abc123", "agent_name": "finance-agent", "result": None,
    "success": None, "latency_ms": None, "retries": 0,
}

sample_state: OrchestratorState = {
    "task_run_id": "test-task-4", "request_text": "test request", "context": {},
    "required": [], "assignments": [sample_assignment], "unfilled": [],
    "completed": [], "failed": [], "consensus_output": None, "status": "running",
}

print("State constructed OK")
print(sample_state)
