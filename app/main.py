import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import redis_bus
from app import registry
from app.analytics.team_graph import (
    build_collaboration_graph,
    render_collaboration_graph,
    render_task_run_summary,
)
from app.database import get_db, init_db, SessionLocal
from app.models import Agent, TaskRun, TeamMembership
from app.orchestrator.graph import orchestrator_graph
from app.orchestrator.state import OrchestratorState
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.scoring.evaluator import update_agent_scores
import seed_agents


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_agents.seed_agents()
    yield


app = FastAPI(title="AI Agent Marketplace", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/app/static", StaticFiles(directory="app/static"), name="app_static")
app.include_router(registry.router)


@app.get("/", response_class=FileResponse)
def root():
    return FileResponse("app/static/index.html")


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_request(payload: AnalyzeRequest, db: Session = Depends(get_db)):
    task_run_id = str(uuid.uuid4())
    task_run = TaskRun(
        id=task_run_id,
        request_text=payload.request_text,
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(task_run)
    db.commit()

    initial_state: OrchestratorState = {
        "task_run_id": task_run_id,
        "request_text": payload.request_text,
        "context": payload.context or {},
        "required": [],
        "assignments": [],
        "unfilled": [],
        "completed": [],
        "failed": [],
        "consensus_output": None,
        "status": "running",
    }

    final_state = await orchestrator_graph.ainvoke(initial_state)

    completed = final_state.get("completed", [])
    failed = final_state.get("failed", [])
    all_assignments = completed + failed

    await update_agent_scores(db, task_run_id, all_assignments)

    task_run = db.query(TaskRun).filter(TaskRun.id == task_run_id).first()
    if task_run:
        task_run.consensus_output = final_state.get("consensus_output", "")
        task_run.status = final_state.get("status", "completed")
        task_run.finished_at = datetime.utcnow()
        db.commit()

    team = [
        {
            "agent_name": a.get("agent_name"),
            "subtask": a.get("subtask"),
            "success": a.get("success"),
        }
        for a in all_assignments
    ]

    return AnalyzeResponse(
        task_run_id=task_run_id,
        team=team,
        consensus_output=final_state.get("consensus_output", ""),
        status=final_state.get("status", "completed"),
        analytics_url=f"/analytics/{task_run_id}",
    )


@app.get("/tasks/{task_run_id}")
def get_task_run(task_run_id: str, db: Session = Depends(get_db)):
    task_run = db.query(TaskRun).filter(TaskRun.id == task_run_id).first()
    if not task_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task run not found"
        )

    memberships = (
        db.query(TeamMembership)
        .filter(TeamMembership.task_run_id == task_run_id)
        .all()
    )

    agent_id_map = {a.id: a.name for a in db.query(Agent).all()}

    team_data = []
    for m in memberships:
        team_data.append(
            {
                "id": m.id,
                "agent_id": m.agent_id,
                "agent_name": agent_id_map.get(m.agent_id, m.agent_id),
                "subtask": m.subtask,
                "role": m.role,
                "replaced_agent_id": m.replaced_agent_id,
                "success": m.success,
                "latency_ms": m.latency_ms,
                "quality_score": m.quality_score,
                "result_summary": m.result_summary,
            }
        )

    return {
        "id": task_run.id,
        "request_text": task_run.request_text,
        "status": task_run.status,
        "consensus_output": task_run.consensus_output,
        "started_at": task_run.started_at,
        "finished_at": task_run.finished_at,
        "team_memberships": team_data,
    }


@app.get("/analytics/network", response_class=HTMLResponse)
def get_network_analytics(db: Session = Depends(get_db)):
    graph = build_collaboration_graph(db)
    html_content = render_collaboration_graph(graph)
    return HTMLResponse(content=html_content)


@app.get("/analytics/{task_run_id}", response_class=HTMLResponse)
def get_task_analytics(task_run_id: str, db: Session = Depends(get_db)):
    html_content = render_task_run_summary(db, task_run_id)
    return HTMLResponse(content=html_content)


@app.get("/a2a-log/{task_run_id}")
def get_a2a_log(task_run_id: str):
    log_entries = redis_bus.get_log(task_run_id)
    return log_entries


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
