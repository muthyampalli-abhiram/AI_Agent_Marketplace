import sys
import asyncio
from pathlib import Path

root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.agents.domain_agents import get_agent_instance
from app.config import settings

AGENTS = [
    "finance-agent",
    "legal-agent",
    "market-agent",
    "technology-agent",
    "hr-agent",
    "risk-agent",
]

async def run_agent_diagnostic():
    print(f"=== Agent Error Diagnostic (GROQ_MODEL={settings.GROQ_MODEL}) ===")
    print(f"GROQ_API_KEY: {settings.GROQ_API_KEY[:12]}...\n")

    # Run all 6 agents concurrently to reproduce exact pipeline load/rate-limiting
    tasks = []
    for i, name in enumerate(AGENTS):
        agent = get_agent_instance(name)
        # We also inspect what happens when _run_llm is directly called to get the exact unhandled exception
        subtask = f"Perform {agent.domain} assessment for acquisition"
        context = {"request": "Analyze this company's acquisition opportunity."}
        tasks.append((name, agent, subtask, context, i * 0.4))

    async def invoke_agent(name, agent, subtask, context, delay):
        if delay > 0:
            await asyncio.sleep(delay)
        
        raw_exception = None
        try:
            # Call _run_llm directly to capture the raw exception before BaseAgent catches it
            res_text = await agent._run_llm(subtask, context)
            status = "SUCCESS"
            err_msg = None
        except Exception as e:
            status = "FAILED"
            raw_exception = e
            err_msg = f"{type(e).__name__}: {str(e)}"
            
        return name, status, err_msg, raw_exception

    results = await asyncio.gather(*[invoke_agent(*t) for t in tasks])

    for name, status, err_msg, raw_exc in results:
        print(f"Agent: {name}")
        print(f"  Status: {status}")
        if err_msg:
            print(f"  Exception Class: {type(raw_exc).__name__ if raw_exc else 'N/A'}")
            print(f"  Raw Error Message: {err_msg}")
        else:
            print("  Output Snippet: Success")
        print("-" * 60)

if __name__ == "__main__":
    asyncio.run(run_agent_diagnostic())
