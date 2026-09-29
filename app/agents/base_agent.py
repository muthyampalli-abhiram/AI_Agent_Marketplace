import asyncio
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app import llm_client
from app import redis_bus
from app.config import settings


@dataclass
class AgentResult:
    agent_name: str
    success: bool
    output: str = ""
    latency_ms: float = 0.0
    error: Optional[str] = None


class BaseAgent:
    name: str = "base-agent"
    domain: str = "general"
    capabilities: List[str] = []
    system_prompt: str = "You are a helpful domain expert agent."
    failure_rate: float = 0.05

    async def invoke(
        self, task_run_id: str, subtask: str, shared_context: Dict[str, Any]
    ) -> AgentResult:
        """
        Invoke the agent for a given subtask and shared context.

        Publishes status events to redis_bus, simulates failure based on failure_rate,
        executes _run_llm on success, and returns an AgentResult without raising exceptions.
        """
        start_time = time.perf_counter()
        redis_bus.publish(
            task_run_id,
            self.name,
            "status",
            {"state": "started", "subtask": subtask},
        )

        try:
            if random.random() < self.failure_rate:
                raise RuntimeError("timed out reaching an upstream data source")

            output = await self._run_llm(subtask, shared_context)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            redis_bus.publish(
                task_run_id,
                self.name,
                "result",
                {"output": output, "latency_ms": latency_ms},
            )

            return AgentResult(
                agent_name=self.name,
                success=True,
                output=output,
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            error_msg = str(e)

            redis_bus.publish(
                task_run_id,
                self.name,
                "error",
                {"error": error_msg, "latency_ms": latency_ms},
            )

            return AgentResult(
                agent_name=self.name,
                success=False,
                error=error_msg,
                latency_ms=latency_ms,
            )

    async def _run_llm(self, subtask: str, shared_context: Dict[str, Any]) -> str:
        """
        Execute LLM call using shared llm_client or fallback to a stub string if API key is not configured.
        """
        api_key = settings.GROQ_API_KEY
        if not api_key or "your_" in api_key or "placeholder" in api_key:
            await asyncio.sleep(0.3)
            return (
                f"[STUB OUTPUT for {self.name}] Subtask: '{subtask}'. "
                f"Analysis based on shared context: {shared_context}. "
                "Assumptions: standard industry baseline. Risks: unverified external factors."
            )

        prompt = (
            f"System Prompt: {self.system_prompt}\n\n"
            f"Shared Context: {shared_context}\n\n"
            f"Subtask: {subtask}\n\n"
            "Please provide a concise structured finding with explicit assumptions and any risks in your area of expertise."
        )

        return await llm_client.complete(prompt, max_tokens=600)
