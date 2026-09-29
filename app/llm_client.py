import asyncio
import re
import time
from typing import Optional

try:
    from groq import Groq, RateLimitError
except ImportError:
    Groq = None
    RateLimitError = Exception

from app.config import settings


def _parse_retry_after(err_msg: str) -> Optional[float]:
    """Parse suggested retry wait time (in seconds) from LLM rate limit error messages."""
    match_sec = re.search(
        r"try again in\s+(?:(\d+(?:\.\d+)?)m)?\s*(\d+(?:\.\d+)?)s",
        err_msg,
        re.IGNORECASE,
    )
    if match_sec:
        try:
            mins = float(match_sec.group(1)) if match_sec.group(1) else 0.0
            secs = float(match_sec.group(2)) if match_sec.group(2) else 0.0
            return mins * 60.0 + secs + 0.5
        except ValueError:
            pass

    match_ms = re.search(
        r"try again in\s+(\d+(?:\.\d+)?)\s*ms",
        err_msg,
        re.IGNORECASE,
    )
    if match_ms:
        try:
            return float(match_ms.group(1)) / 1000.0 + 0.1
        except ValueError:
            pass

    return None


async def complete(prompt: str, max_tokens: int = 600) -> str:
    """
    Shared LLM completion wrapper using Groq API SDK.

    Calls settings.GROQ_MODEL directly with up to 2 retries on rate limit (HTTP 429).
    If GROQ_API_KEY is not configured, returns a stub string after simulating latency.
    """
    api_key = settings.GROQ_API_KEY
    use_llm = (
        api_key
        and "your_" not in api_key
        and "placeholder" not in api_key
        and Groq is not None
    )

    if not use_llm:
        await asyncio.sleep(0.3)
        return (
            "[STUB OUTPUT] Analysis completed based on provided input prompt. "
            "Assumptions: standard industry baseline. Risks: unverified external factors."
        )

    def _call_groq() -> str:
        client = Groq(api_key=api_key, timeout=3.0, max_retries=0)
        model = settings.GROQ_MODEL
        max_attempts = 3
        last_err = None

        for attempt in range(max_attempts):
            try:
                response = client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                last_err = e
                # Retry on rate limit (HTTP 429) or RateLimitError
                is_rate_limit = (
                    isinstance(e, RateLimitError)
                    or "429" in str(e)
                    or "rate_limit" in str(e).lower()
                )
                if is_rate_limit and attempt < max_attempts - 1:
                    wait_time = _parse_retry_after(str(e))
                    if wait_time is None:
                        wait_time = 1.5 * (attempt + 1)
                    time.sleep(wait_time)
                else:
                    raise e
        raise last_err

    return await asyncio.to_thread(_call_groq)
