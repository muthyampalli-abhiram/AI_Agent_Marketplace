import asyncio
from app.agents.domain_agents import DOMAIN_AGENT_CLASSES, get_agent_instance

async def main():
    print(f"Total domain agent classes: {len(DOMAIN_AGENT_CLASSES)}")
    for cls in DOMAIN_AGENT_CLASSES:
        print(f"- {cls.name} ({cls.domain}): {cls.capabilities}")

    agent = get_agent_instance("finance-agent")
    agent.failure_rate = 0.0
    result = await agent.invoke("test-task-3", "assess valuation risk", {"request": "test run"})
    print("\nInvoked finance-agent -> success:", result.success)
    print("output:", result.output[:200])

    try:
        get_agent_instance("nonexistent-agent")
        print("ERROR: should have raised ValueError")
    except ValueError as e:
        print(f"\nCorrectly raised ValueError: {e}")

asyncio.run(main())
