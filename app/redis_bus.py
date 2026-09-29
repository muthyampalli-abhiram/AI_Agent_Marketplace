"""
In-memory stand-in for a Redis-backed Agent-to-Agent (A2A) message bus.

This module provides identical function signatures to a Redis-backed implementation
(using redis-py pub/sub + RPUSH/LRANGE/SETEX) so that it can be seamlessly swapped for
a real Redis implementation later (e.g. via Docker Compose) without changing any calling code.
"""

import time
import threading
from typing import Any, Dict, List, Optional

_lock = threading.Lock()
_message_logs: Dict[str, List[Dict[str, Any]]] = {}
_agent_statuses: Dict[str, Dict[str, Any]] = {}


def channel_for(task_run_id: str) -> str:
    """Return the channel topic name for a given task run ID."""
    return f"a2a:{task_run_id}"


def publish(
    task_run_id: str,
    sender: str,
    event_type: str,
    payload: Any,
    to: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Publish an A2A message to the log for a given task run.

    Builds a message dict containing from, to, type, payload, and timestamp,
    then appends it to the in-memory log for task_run_id.
    """
    msg = {
        "from": sender,
        "to": to,
        "type": event_type,
        "payload": payload,
        "ts": time.time(),
    }
    with _lock:
        if task_run_id not in _message_logs:
            _message_logs[task_run_id] = []
        _message_logs[task_run_id].append(msg)
    return msg


def get_log(task_run_id: str) -> List[Dict[str, Any]]:
    """Return the full list of events logged for a given task_run_id."""
    with _lock:
        return list(_message_logs.get(task_run_id, []))


def set_agent_status(agent_name: str, status: str, ttl_seconds: int = 120) -> None:
    """Store agent status in memory with an expiration timestamp (TTL)."""
    expires_at = time.time() + ttl_seconds
    with _lock:
        _agent_statuses[agent_name] = {
            "status": status,
            "expires_at": expires_at,
        }


def get_agent_status(agent_name: str) -> Optional[str]:
    """
    Retrieve agent status from memory.

    Returns the status string if found and not expired; otherwise returns None.
    """
    now = time.time()
    with _lock:
        info = _agent_statuses.get(agent_name)
        if not info:
            return None
        if now >= info["expires_at"]:
            del _agent_statuses[agent_name]
            return None
        return info["status"]
