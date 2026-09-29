import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
import seed_agents

EXPECTED_AGENTS = {
    "finance-agent",
    "legal-agent",
    "market-agent",
    "technology-agent",
    "hr-agent",
    "risk-agent",
}


def run_smoke_test():
    init_db()
    seed_agents.seed_agents()

    client = TestClient(app)
    passed_checks = 0
    total_checks = 5
    task_run_id = None

    # Check 1: GET /agents
    try:
        res = client.get("/agents")
        if res.status_code != 200:
            raise AssertionError(f"Expected status 200, got {res.status_code}")
        agents = res.json()
        agent_names = {a["name"] for a in agents if a.get("status") == "active"}
        missing = EXPECTED_AGENTS - agent_names
        if missing:
            raise AssertionError(f"Missing active agents: {missing}")
        print("PASS: Check 1 - GET /agents returns all 6 active agents")
        passed_checks += 1
    except Exception as e:
        print(f"FAIL: Check 1 - GET /agents failed: {e}")

    # Check 2: POST /analyze
    try:
        res = client.post(
            "/analyze",
            json={"request_text": "Analyze this company's acquisition opportunity."},
        )
        if res.status_code != 200:
            raise AssertionError(f"Expected status 200, got {res.status_code}")
        data = res.json()
        task_run_id = data.get("task_run_id")
        team = data.get("team", [])
        consensus_output = data.get("consensus_output", "")

        if not task_run_id:
            raise AssertionError("Missing task_run_id in response")
        if len(team) < 6:
            raise AssertionError(f"Expected at least 6 team members, got {len(team)}")
        if not consensus_output or not consensus_output.strip():
            raise AssertionError("Empty consensus_output in response")

        print(f"PASS: Check 2 - POST /analyze succeeded with {len(team)} team members (task_run_id: {task_run_id})")
        print("\n--- Consensus Output (first 300 chars) ---")
        safe_text = consensus_output[:300].encode("ascii", errors="replace").decode("ascii")
        print(safe_text)
        print("------------------------------------------\n")
        passed_checks += 1
    except Exception as e:
        print(f"FAIL: Check 2 - POST /analyze failed: {e}")

    # Check 3: GET /tasks/{task_run_id}
    try:
        if not task_run_id:
            raise AssertionError("Cannot test GET /tasks/{task_run_id} because POST /analyze failed")
        res = client.get(f"/tasks/{task_run_id}")
        if res.status_code != 200:
            raise AssertionError(f"Expected status 200, got {res.status_code}")
        data = res.json()
        if data.get("status") not in ("completed", "completed_with_errors"):
            raise AssertionError(f"Expected status 'completed' or 'completed_with_errors', got '{data.get('status')}'")
        memberships = data.get("team_memberships", [])
        if len(memberships) < 6:
            raise AssertionError(f"Expected at least 6 team_memberships, got {len(memberships)}")

        print(f"PASS: Check 3 - GET /tasks/{task_run_id} returned status '{data.get('status')}' and {len(memberships)} memberships")
        passed_checks += 1
    except Exception as e:
        print(f"FAIL: Check 3 - GET /tasks/{{task_run_id}} failed: {e}")

    # Check 4: GET /a2a-log/{task_run_id}
    try:
        if not task_run_id:
            raise AssertionError("Cannot test GET /a2a-log/{task_run_id} because POST /analyze failed")
        res = client.get(f"/a2a-log/{task_run_id}")
        if res.status_code != 200:
            raise AssertionError(f"Expected status 200, got {res.status_code}")
        logs = res.json()
        events_per_agent = {}
        for entry in logs:
            sender = entry.get("from")
            events_per_agent[sender] = events_per_agent.get(sender, 0) + 1

        if len(logs) < 12:
            raise AssertionError(f"Expected at least 12 total log entries (2 per agent), got {len(logs)}")
        for agent_name in EXPECTED_AGENTS:
            if events_per_agent.get(agent_name, 0) < 2:
                raise AssertionError(
                    f"Agent '{agent_name}' has fewer than 2 log events ({events_per_agent.get(agent_name, 0)})"
                )

        print(f"PASS: Check 4 - GET /a2a-log/{task_run_id} returned at least 2 events per team member")
        passed_checks += 1
    except Exception as e:
        print(f"FAIL: Check 4 - GET /a2a-log/{{task_run_id}} failed: {e}")

    # Check 5: GET /analytics/network and /analytics/{task_run_id}
    try:
        if not task_run_id:
            raise AssertionError("Cannot test GET /analytics/{task_run_id} because POST /analyze failed")

        res_net = client.get("/analytics/network")
        if res_net.status_code != 200:
            raise AssertionError(f"GET /analytics/network returned status {res_net.status_code}")
        if len(res_net.text) <= 500:
            raise AssertionError(f"GET /analytics/network returned short HTML ({len(res_net.text)} chars)")

        res_task = client.get(f"/analytics/{task_run_id}")
        if res_task.status_code != 200:
            raise AssertionError(f"GET /analytics/{task_run_id} returned status {res_task.status_code}")
        if len(res_task.text) <= 500:
            raise AssertionError(f"GET /analytics/{task_run_id} returned short HTML ({len(res_task.text)} chars)")

        print("PASS: Check 5 - GET /analytics/network and /analytics/{id} returned 200 with rich HTML content")
        passed_checks += 1
    except Exception as e:
        print(f"FAIL: Check 5 - GET /analytics endpoints failed: {e}")

    print(f"\nSummary: {passed_checks}/{total_checks} checks passed")
    if passed_checks < total_checks:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    run_smoke_test()
