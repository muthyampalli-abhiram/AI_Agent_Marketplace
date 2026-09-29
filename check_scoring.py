import asyncio
from app.database import SessionLocal, init_db
from app.models import Agent
from app.orchestrator.graph import orchestrator_graph
from app.scoring.evaluator import update_agent_scores
import seed_agents

async def main():
    init_db()
    seed_agents.seed_agents()

    db = SessionLocal()
    finance_before = db.query(Agent).filter(Agent.name == "finance-agent").first()
    print(f"finance-agent BEFORE: score={finance_before.performance_score}, tasks={finance_before.total_tasks}, failures={finance_before.total_failures}")
    db.close()

    initial_state = {
        "task_run_id": "test-task-8",
        "request_text": "Analyze this company's acquisition opportunity.",
        "context": {}, "required": [], "assignments": [], "unfilled": [],
        "completed": [], "failed": [], "consensus_output": None, "status": "running",
    }
    final_state = await orchestrator_graph.ainvoke(initial_state)

    db = SessionLocal()
    all_assignments = final_state["completed"] + final_state["failed"]
    await update_agent_scores(db, "test-task-8", all_assignments)

    finance_after = db.query(Agent).filter(Agent.name == "finance-agent").first()
    print(f"finance-agent AFTER:  score={finance_after.performance_score}, tasks={finance_after.total_tasks}, failures={finance_after.total_failures}")
    db.close()

asyncio.run(main())
