from app.redis_bus import publish, get_log, set_agent_status, get_agent_status

publish("test-task-1", "finance-agent", "status", {"state": "started", "subtask": "value the target"})
publish("test-task-1", "finance-agent", "result", {"output": "estimated valuation: $42M"})

log = get_log("test-task-1")
print(f"Log entries: {len(log)}")
for entry in log:
    print(entry)

set_agent_status("finance-agent", "busy")
print("Status:", get_agent_status("finance-agent"))