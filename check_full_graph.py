import asyncio
from app.orchestrator.graph import orchestrator_graph
from app.database import init_db
import seed_agents

async def main():
    init_db()
    seed_agents.seed_agents()

    initial_state = {
        "task_run_id": "test-task-7",
        "request_text": "Analyze this company's acquisition opportunity.",
        "context": {}, "required": [], "assignments": [], "unfilled": [],
        "completed": [], "failed": [], "consensus_output": None, "status": "running",
    }
    final_state = await orchestrator_graph.ainvoke(initial_state)
    print("Status:", final_state["status"])
    print("Completed:", len(final_state["completed"]))
    print("Failed:", len(final_state["failed"]))
    print("\n--- CONSENSUS OUTPUT ---\n")
    print(final_state["consensus_output"])

asyncio.run(main())
