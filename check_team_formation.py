import asyncio
from app.orchestrator.graph import decompose_node, form_team_node

async def main():
    state = {
        "task_run_id": "test-task-5",
        "request_text": "Analyze this company's acquisition opportunity.",
        "context": {}, "required": [], "assignments": [], "unfilled": [],
        "completed": [], "failed": [], "consensus_output": None, "status": "running",
    }

    decompose_result = await decompose_node(state)
    state.update(decompose_result)
    print(f"Required: {len(state['required'])} items")

    team_result = await form_team_node(state)
    state.update(team_result)
    print(f"\nAssignments: {len(state['assignments'])}")
    for a in state["assignments"]:
        print(f"- {a['capability']} -> {a['agent_name']}")
    print(f"\nUnfilled: {len(state['unfilled'])}")
    for u in state["unfilled"]:
        print(f"- {u}")

asyncio.run(main())
