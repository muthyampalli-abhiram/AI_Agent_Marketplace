import asyncio
from app.orchestrator.graph import decompose_node, form_team_node, delegate_and_execute_node, handle_failures_node
from app.agents.domain_agents import get_agent_instance

from app.database import init_db
import seed_agents

async def main():
    init_db()
    seed_agents.seed_agents()
    state = {
        "task_run_id": "test-task-6",
        "request_text": "Analyze this company's acquisition opportunity.",
        "context": {}, "required": [], "assignments": [], "unfilled": [],
        "completed": [], "failed": [], "consensus_output": None, "status": "running",
    }
    state.update(await decompose_node(state))
    state.update(await form_team_node(state))

    # Force the finance-agent to always fail for this run, to test replacement.
    original_agent = get_agent_instance("finance-agent")
    for a in state["assignments"]:
        if a["agent_name"] == "finance-agent":
            pass  # failure_rate is set on the class instance created inside the node, so patch the class instead
    import app.agents.domain_agents as da
    da.FinanceAgent.failure_rate = 1.0  # force it to always fail
    for cls in [da.LegalAgent, da.MarketAgent, da.TechnologyAgent, da.HRAgent, da.RiskAgent]:
        cls.failure_rate = 0.0  # keep everyone else reliable for a clean test

    exec_result = await delegate_and_execute_node(state)
    state.update(exec_result)
    print(f"Completed after first pass: {len(state['completed'])}")
    print(f"Failed after first pass: {len(state['failed'])}")
    for f in state["failed"]:
        print(f"- FAILED: {f['capability']} via {f['agent_name']} (retries={f['retries']})")

    if state["failed"]:
        # Give the replacement a fair shot at succeeding.
        da.FinanceAgent.failure_rate = 0.0
        retry_result = await handle_failures_node(state)
        state.update(retry_result)
        print(f"\nCompleted after retry: {len(state['completed'])}")
        print(f"Permanently failed after retry: {len(state['failed'])}")
        for a in state["completed"]:
            if a["retries"] > 0:
                print(f"- REPLACED: {a['capability']} now via {a['agent_name']} (retries={a['retries']})")

asyncio.run(main())
