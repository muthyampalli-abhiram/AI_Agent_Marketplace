import asyncio
import re
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app import llm_client
from app.config import settings
from app.models import Agent, TaskRun, TeamMembership


async def _judge_quality(subtask: str, output: str) -> float:
    """Evaluate quality score (0.0 - 1.0) using LLM-as-judge or return fallback 0.6."""
    api_key = settings.GROQ_API_KEY
    use_llm = (
        api_key
        and "your_" not in api_key
        and "placeholder" not in api_key
    )
    if not use_llm:
        return 0.6

    prompt = (
        f"Subtask: '{subtask}'\n"
        f"Agent Output: '{output}'\n\n"
        "Rate how relevant, structured, and well-reasoned this output is for the subtask. "
        "Return ONLY a single floating-point number between 0.0 and 1.0 (e.g., 0.85)."
    )

    try:
        raw_resp = await llm_client.complete(prompt, max_tokens=50)
        match = re.search(r"\b(0(?:\.\d+)?|1(?:\.0+)?)\b", raw_resp.strip())
        if match:
            score = float(match.group(1))
            return max(0.0, min(1.0, score))
    except Exception:
        pass

    return 0.6


def _compute_latency_component(latency_ms: float) -> float:
    if latency_ms <= 5000:
        return 1.0
    if latency_ms >= 30000:
        return 0.0
    val = 1.0 - ((latency_ms - 5000.0) / 25000.0)
    return max(0.0, min(1.0, val))


async def update_agent_scores(
    db_session: Session, task_run_id: str, assignments: List[Dict[str, Any]]
) -> None:
    """
    Update performance_score, total_tasks, and total_failures for agents involved in task run assignments.
    Uses an exponential moving average (alpha=0.3) over success, latency, and quality components.
    Also persists TaskRun and TeamMembership records to DB.
    """
    alpha = 0.3

    task_run = db_session.query(TaskRun).filter(TaskRun.id == task_run_id).first()
    if not task_run:
        task_run = TaskRun(
            id=task_run_id,
            request_text="Orchestration Task Run",
            status="completed",
        )
        db_session.add(task_run)
        db_session.flush()

    for assignment in assignments:
        agent_id = assignment.get("agent_id")
        agent_name = assignment.get("agent_name")

        agent = None
        if agent_id:
            agent = db_session.query(Agent).filter(Agent.id == agent_id).first()
        if not agent and agent_name:
            agent = db_session.query(Agent).filter(Agent.name == agent_name).first()

        if not agent:
            continue

        success = bool(assignment.get("success", False))
        latency_ms = float(assignment.get("latency_ms", 0.0) or 0.0)
        subtask = assignment.get("subtask", "")
        output = assignment.get("result", "") or ""

        success_comp = 1.0 if success else 0.0
        latency_comp = _compute_latency_component(latency_ms)

        if success:
            quality_score = await _judge_quality(subtask, output)
        else:
            quality_score = 0.0

        w_sum = settings.W_SUCCESS + settings.W_LATENCY + settings.W_QUALITY
        w_success = settings.W_SUCCESS / w_sum
        w_latency = settings.W_LATENCY / w_sum
        w_quality = settings.W_QUALITY / w_sum

        weighted_blend = (
            (w_success * success_comp)
            + (w_latency * latency_comp)
            + (w_quality * quality_score)
        )

        old_score = (
            agent.performance_score
            if agent.performance_score is not None
            else 0.7
        )
        new_score = ((1.0 - alpha) * old_score) + (alpha * weighted_blend)

        agent.performance_score = round(new_score, 4)
        agent.total_tasks = (agent.total_tasks or 0) + 1
        if not success:
            agent.total_failures = (agent.total_failures or 0) + 1

        membership = (
            db_session.query(TeamMembership)
            .filter(
                TeamMembership.task_run_id == task_run_id,
                TeamMembership.agent_id == agent.id,
            )
            .first()
        )
        if not membership:
            membership = TeamMembership(
                task_run_id=task_run_id,
                agent_id=agent.id,
                subtask=subtask,
                role="contributor",
                replaced_agent_id=assignment.get("replaced_agent_id"),
                result_summary=output[:250] if output else None,
                success=success,
                latency_ms=latency_ms,
                quality_score=quality_score,
            )
            db_session.add(membership)
        else:
            membership.subtask = subtask
            membership.success = success
            membership.latency_ms = latency_ms
            membership.quality_score = quality_score
            membership.result_summary = output[:250] if output else None

    db_session.commit()
