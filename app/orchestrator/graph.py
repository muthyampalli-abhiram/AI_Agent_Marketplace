import asyncio
from typing import Any, Dict, List
from langgraph.graph import StateGraph, START, END

from app import redis_bus
from app import llm_client

from app.agents.base_agent import AgentResult
from app.agents.domain_agents import get_agent_instance
from app.config import settings
from app.database import SessionLocal
from app.models import Agent
from app.orchestrator.capability_matcher import (
    canonical_domain,
    decompose_request,
    score_agent,
)
from app.orchestrator.state import OrchestratorState, SubtaskAssignment


async def decompose_node(state: OrchestratorState) -> Dict[str, Any]:
    """Decompose request_text into required specialist domains/subtasks."""
    required = await decompose_request(state["request_text"])
    return {"required": required}


async def form_team_node(state: OrchestratorState) -> Dict[str, Any]:
    """Form a team of active agents matching required capabilities."""
    db = SessionLocal()
    try:
        active_agents = db.query(Agent).filter(Agent.status == "active").all()
        scored_assignments: List[tuple[float, SubtaskAssignment]] = []
        unfilled: List[Dict[str, Any]] = []
        assigned_agent_ids: set[str] = set()

        for item in state.get("required", []):
            req_domain = (item.get("domain") or "").lower().strip()
            capability = item.get("capability") or item.get("domain") or ""
            target_domain = canonical_domain(req_domain) or canonical_domain(capability)

            best_agent = None
            max_score = -1.0
            best_domain_match = False

            # Prefer unassigned agents to prevent duplicate assignments when unique agents exist
            unassigned = [a for a in active_agents if a.id not in assigned_agent_ids]
            candidate_pool = unassigned if unassigned else active_agents

            # Domain specialists must always outrank cross-domain agents for their own domain
            matching_domain_agents = [
                a for a in candidate_pool
                if target_domain and canonical_domain(a.domain) == target_domain
            ]

            best_agent = None
            max_score = -1.0

            if matching_domain_agents:
                best_agent = max(
                    matching_domain_agents,
                    key=lambda a: (a.performance_score if a.performance_score is not None else 0.7)
                )
                max_score = score_agent(capability, best_agent, domain=req_domain)
            else:
                for agent in candidate_pool:
                    s = score_agent(capability, agent, domain=req_domain)
                    if s > max_score:
                        max_score = s
                        best_agent = agent

            if best_agent and max_score >= settings.MIN_CAPABILITY_SCORE:
                assigned_agent_ids.add(best_agent.id)
                assignment: SubtaskAssignment = {
                    "domain": item.get("domain", ""),
                    "capability": item.get("capability", ""),
                    "subtask": item.get("subtask", ""),
                    "agent_id": best_agent.id,
                    "agent_name": best_agent.name,
                    "result": None,
                    "success": None,
                    "latency_ms": None,
                    "retries": 0,
                }
                scored_assignments.append((max_score, assignment))
            else:
                unfilled.append(item)

        assignments: List[SubtaskAssignment] = []
        if len(scored_assignments) > settings.MAX_TEAM_SIZE:
            scored_assignments.sort(key=lambda x: x[0], reverse=True)
            kept = scored_assignments[: settings.MAX_TEAM_SIZE]
            dropped = scored_assignments[settings.MAX_TEAM_SIZE :]

            assignments = [item[1] for item in kept]
            for _, overflow_assignment in dropped:
                unfilled.append(
                    {
                        "domain": overflow_assignment["domain"],
                        "capability": overflow_assignment["capability"],
                        "subtask": overflow_assignment["subtask"],
                    }
                )
        else:
            assignments = [item[1] for item in scored_assignments]

        return {"assignments": assignments, "unfilled": unfilled}
    finally:
        db.close()


async def _invoke_single_assignment(
    task_run_id: str, request_text: str, assignment: SubtaskAssignment, delay: float = 0.0
) -> tuple[SubtaskAssignment, AgentResult]:
    if delay > 0:
        await asyncio.sleep(delay)
    agent_name = assignment.get("agent_name") or ""
    try:
        agent_instance = get_agent_instance(agent_name)
        result = await asyncio.wait_for(
            agent_instance.invoke(
                task_run_id,
                assignment["subtask"],
                shared_context={"request": request_text},
            ),
            timeout=settings.TASK_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        redis_bus.publish(
            task_run_id,
            agent_name,
            "error",
            {"error": "timed out", "latency_ms": settings.TASK_TIMEOUT_SECONDS * 1000.0},
        )
        result = AgentResult(
            agent_name=agent_name,
            success=False,
            error="timed out",
            latency_ms=settings.TASK_TIMEOUT_SECONDS * 1000.0,
        )
    except Exception as e:
        redis_bus.publish(
            task_run_id,
            agent_name,
            "error",
            {"error": str(e), "latency_ms": 0.0},
        )
        result = AgentResult(
            agent_name=agent_name,
            success=False,
            error=str(e),
            latency_ms=0.0,
        )

    return assignment, result


async def delegate_and_execute_node(state: OrchestratorState) -> Dict[str, Any]:
    """Execute all team subtasks concurrently with slight staggering."""
    task_run_id = state.get("task_run_id", "")
    request_text = state.get("request_text", "")
    assignments = state.get("assignments", [])

    tasks = [
        _invoke_single_assignment(task_run_id, request_text, a, delay=i * 1.5)
        for i, a in enumerate(assignments)
    ]
    results = await asyncio.gather(*tasks)

    completed: List[SubtaskAssignment] = []
    failed: List[SubtaskAssignment] = []

    for assignment, res in results:
        updated_assignment = dict(assignment)
        updated_assignment["result"] = res.output if res.success else None
        updated_assignment["success"] = res.success
        updated_assignment["latency_ms"] = res.latency_ms

        if res.success:
            completed.append(updated_assignment)
        else:
            failed.append(updated_assignment)

    return {"completed": completed, "failed": failed}


async def handle_failures_node(state: OrchestratorState) -> Dict[str, Any]:
    """Handle failed assignments by attempting agent replacement and retry."""
    task_run_id = state.get("task_run_id", "")
    request_text = state.get("request_text", "")
    failed_assignments = state.get("failed", [])
    existing_completed = list(state.get("completed", []))

    newly_completed: List[SubtaskAssignment] = []
    permanently_failed: List[SubtaskAssignment] = []

    # Track agent IDs already completed in the team
    used_agent_ids = {c["agent_id"] for c in existing_completed if c.get("agent_id")}

    db = SessionLocal()
    try:
        active_agents = db.query(Agent).filter(Agent.status == "active").all()

        for assignment in failed_assignments:
            current_retries = assignment.get("retries", 0)
            if current_retries < settings.MAX_AGENT_RETRIES:
                failed_agent_id = assignment.get("agent_id")

                # Priority 1: Unassigned active agents not in team and not failed
                candidates = [a for a in active_agents if a.id not in used_agent_ids and a.id != failed_agent_id]

                # Priority 2: Retry with the original failed agent (for transient failure recovery)
                if not candidates:
                    candidates = [a for a in active_agents if a.id == failed_agent_id]

                # Priority 3: Any active candidate not failed
                if not candidates:
                    candidates = [a for a in active_agents if a.id != failed_agent_id]

                capability = assignment.get("capability") or assignment.get("domain") or ""
                req_domain = (assignment.get("domain") or "").lower().strip()
                target_domain = canonical_domain(req_domain) or canonical_domain(capability)

                matching_domain_candidates = [
                    c for c in candidates
                    if target_domain and canonical_domain(c.domain) == target_domain
                ]

                best_agent = None
                max_score = -1.0

                if matching_domain_candidates:
                    best_agent = max(
                        matching_domain_candidates,
                        key=lambda a: (a.performance_score if a.performance_score is not None else 0.7)
                    )
                    max_score = score_agent(capability, best_agent, domain=req_domain)
                else:
                    for candidate in candidates:
                        s = score_agent(capability, candidate, domain=req_domain)
                        if s > max_score:
                            max_score = s
                            best_agent = candidate

                if best_agent and max_score >= settings.MIN_CAPABILITY_SCORE:
                    used_agent_ids.add(best_agent.id)
                    updated_assignment = dict(assignment)
                    updated_assignment["agent_id"] = best_agent.id
                    updated_assignment["agent_name"] = best_agent.name
                    updated_assignment["retries"] = current_retries + 1

                    _, res = await _invoke_single_assignment(
                        task_run_id, request_text, updated_assignment
                    )
                    updated_assignment["result"] = res.output if res.success else None
                    updated_assignment["success"] = res.success
                    updated_assignment["latency_ms"] = res.latency_ms

                    if res.success:
                        newly_completed.append(updated_assignment)
                    else:
                        permanently_failed.append(updated_assignment)
                else:
                    updated_assignment = dict(assignment)
                    updated_assignment["retries"] = current_retries + 1
                    permanently_failed.append(updated_assignment)
            else:
                updated_assignment = dict(assignment)
                updated_assignment["retries"] = current_retries + 1
                permanently_failed.append(updated_assignment)

        return {
            "completed": existing_completed + newly_completed,
            "failed": permanently_failed,
        }
    finally:
        db.close()


async def generate_consensus_node(state: OrchestratorState) -> Dict[str, Any]:
    """Synthesize completed agent findings into a unified consensus report."""
    request_text = state.get("request_text", "")
    completed = state.get("completed", [])
    unfilled = state.get("unfilled", [])
    failed = state.get("failed", [])

    unfilled_info = [
        f"{u.get('domain', 'unknown')}: {u.get('subtask', 'unfilled')}" for u in unfilled
    ]
    failed_info = [
        f"{f.get('domain', f.get('capability', 'unknown'))} via {f.get('agent_name', 'agent')}"
        for f in failed
    ]

    api_key = settings.GROQ_API_KEY
    has_api_key = bool(
        api_key
        and "your_" not in api_key
        and "placeholder" not in api_key
    )

    if has_api_key and completed:
        try:
            findings_str = "\n\n".join(
                f"=== Domain: {c['domain']} (Agent: {c['agent_name']}) ===\nSubtask: {c['subtask']}\nResult:\n{(c.get('result') or '')[:400]}"
                for c in completed
            )
            gaps_str = ""
            if unfilled_info:
                gaps_str += f"\nUnfilled Capabilities: {', '.join(unfilled_info)}"
            if failed_info:
                gaps_str += f"\nFailed Capabilities: {', '.join(failed_info)}"

            prompt = (
                f"Original User Request: '{request_text}'\n\n"
                f"Agent Domain Findings:\n{findings_str}\n"
                f"{gaps_str}\n\n"
                "Please synthesize these domain findings into a single unified recommendation. "
                "Explicitly include:\n"
                "1. Where the domain findings agree\n"
                "2. Any contradictions between domains and how you resolve them\n"
                "3. The overall recommendation\n"
                "4. An explicit list of unresolved risks/gaps (including any uncovered/failed capabilities listed above).\n"
            )

            consensus_output = await llm_client.complete(prompt, max_tokens=1000)
            return {"consensus_output": consensus_output, "status": "completed"}
        except Exception as e:
            print(f"[generate_consensus_node error] {e}")
            header = f"[CONSENSUS SYNTHESIS FAILED - see error below]\nError: {e}"
            lines = [
                header,
                f"Request: {request_text}\n",
                "Completed Domain Findings:",
            ]
            for c in completed:
                lines.append(f"- [{c['domain']} - {c['agent_name']}] {c.get('result', '')}")

            if unfilled_info or failed_info:
                lines.append("\nUncovered Capabilities / Gaps:")
                for u in unfilled_info:
                    lines.append(f"- Unfilled: {u}")
                for f in failed_info:
                    lines.append(f"- Failed: {f}")

            consensus_output = "\n".join(lines)
            return {"consensus_output": consensus_output, "status": "completed_with_errors"}

    # Fallback concatenation when no API key is configured or no completed findings
    header = (
        "[UNSYNTHESIZED FALLBACK CONSENSUS - NO LLM API KEY CONFIGURED]"
        if not has_api_key
        else "[UNSYNTHESIZED FALLBACK CONSENSUS - NO COMPLETED FINDINGS]"
    )
    lines = [
        header,
        f"Request: {request_text}\n",
        "Completed Domain Findings:",
    ]
    for c in completed:
        lines.append(f"- [{c['domain']} - {c['agent_name']}] {c.get('result', '')}")

    if unfilled_info or failed_info:
        lines.append("\nUncovered Capabilities / Gaps:")
        for u in unfilled_info:
            lines.append(f"- Unfilled: {u}")
        for f in failed_info:
            lines.append(f"- Failed: {f}")

    consensus_output = "\n".join(lines)
    return {"consensus_output": consensus_output, "status": "completed"}


def route_after_execution(state: OrchestratorState) -> str:
    if state.get("failed"):
        return "handle_failures"
    return "generate_consensus"


builder = StateGraph(OrchestratorState)
builder.add_node("decompose", decompose_node)
builder.add_node("form_team", form_team_node)
builder.add_node("delegate_and_execute", delegate_and_execute_node)
builder.add_node("handle_failures", handle_failures_node)
builder.add_node("generate_consensus", generate_consensus_node)

builder.add_edge(START, "decompose")
builder.add_edge("decompose", "form_team")
builder.add_edge("form_team", "delegate_and_execute")
builder.add_conditional_edges(
    "delegate_and_execute",
    route_after_execution,
    {
        "handle_failures": "handle_failures",
        "generate_consensus": "generate_consensus",
    },
)
builder.add_edge("handle_failures", "generate_consensus")
builder.add_edge("generate_consensus", END)

orchestrator_graph = builder.compile()
