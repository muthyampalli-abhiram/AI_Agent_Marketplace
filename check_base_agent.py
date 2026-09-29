import asyncio
from app.agents.base_agent import BaseAgent

class DummyAgent(BaseAgent):
    name = "dummy-agent"
    domain = "test"
    capabilities = ["testing"]
    system_prompt = "You are a test agent."
    failure_rate = 0.0  # force success for this check

async def main():
    agent = DummyAgent()
    result = await agent.invoke("test-task-2", "say hello", {"request": "test run"})
    print("success:", result.success)
    print("output:", result.output)
    print("latency_ms:", result.latency_ms)

asyncio.run(main())
