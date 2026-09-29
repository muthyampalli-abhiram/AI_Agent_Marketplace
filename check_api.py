from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

resp = client.get("/agents")
print("GET /agents:", resp.status_code, "- count:", len(resp.json()))

resp = client.post("/analyze", json={"request_text": "Analyze this company's acquisition opportunity."})
print("\nPOST /analyze:", resp.status_code)
data = resp.json()
task_run_id = data["task_run_id"]
print("task_run_id:", task_run_id)
print("team:")
for member in data["team"]:
    print(f"  - {member['agent_name']}: success={member['success']}")
print("\nconsensus_output (first 300 chars):")
print(data["consensus_output"][:300])

resp = client.get(f"/tasks/{task_run_id}")
print("\nGET /tasks/{{id}}:", resp.status_code, "- status:", resp.json()["status"])

resp = client.get(f"/a2a-log/{task_run_id}")
print("GET /a2a-log/{{id}}:", resp.status_code, "- entries:", len(resp.json()))

resp = client.get("/analytics/network")
print("GET /analytics/network:", resp.status_code, "- length:", len(resp.text))

resp = client.get(f"/analytics/{task_run_id}")
print(f"GET /analytics/{{id}}:", resp.status_code, "- length:", len(resp.text))
