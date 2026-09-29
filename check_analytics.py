import asyncio
from app.database import SessionLocal, init_db
from app.analytics.team_graph import build_collaboration_graph, render_collaboration_graph, render_task_run_summary
from app.orchestrator.graph import orchestrator_graph
from app.scoring.evaluator import update_agent_scores
import seed_agents

async def setup_data():
    init_db()
    seed_agents.seed_agents()
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
    db.close()

asyncio.run(setup_data())

db = SessionLocal()
graph = build_collaboration_graph(db)
print(f"Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

html = render_collaboration_graph(graph)
with open("collaboration_graph.html", "w", encoding="utf-8") as f:
    f.write(html)
print("Wrote collaboration_graph.html")

summary_html = render_task_run_summary(db, "test-task-8")
with open("task_summary.html", "w", encoding="utf-8") as f:
    f.write(summary_html)
print("Wrote task_summary.html")
db.close()
