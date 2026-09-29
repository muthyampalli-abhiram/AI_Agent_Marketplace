import sys
import asyncio
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Agent
from app.orchestrator.graph import form_team_node, handle_failures_node, generate_consensus_node
from app.orchestrator.state import OrchestratorState


def test_specialist_vs_generalist():
    # Setup in-memory SQLite DB
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    # Insert test agents:
    # 1. True domain specialist with low performance_score=0.0
    spec_agent = Agent(
        id="spec-finance-001",
        name="finance-specialist-agent",
        domain="finance",
        capabilities=["financial_diligence", "valuation"],
        status="active",
        performance_score=0.0,
    )
    # 2. Cross-domain generalist with high performance_score=1.0 and overlapping capability
    gen_agent = Agent(
        id="gen-tech-001",
        name="tech-generalist-agent",
        domain="technology",
        capabilities=["financial_diligence", "tech_stack"],
        status="active",
        performance_score=1.0,
    )
    db.add(spec_agent)
    db.add(gen_agent)
    db.commit()

    print("--- Test Scenario Setup ---")
    print(f"Domain Specialist: {spec_agent.name} (domain={spec_agent.domain}, perf_score={spec_agent.performance_score})")
    print(f"Cross-Domain Generalist: {gen_agent.name} (domain={gen_agent.domain}, perf_score={gen_agent.performance_score}, caps={gen_agent.capabilities})")
    print("----------------------------\n")

    # Override SessionLocal in graph module temporarily
    import app.orchestrator.graph as graph_module
    orig_session_local = graph_module.SessionLocal
    graph_module.SessionLocal = TestingSessionLocal

    try:
        # Test 1: form_team_node selection
        state: OrchestratorState = {
            "task_run_id": "test-run-1",
            "request_text": "Need financial diligence for M&A",
            "context": {},
            "required": [
                {
                    "domain": "finance",
                    "capability": "financial_diligence",
                    "subtask": "Analyze financial balance sheet",
                }
            ],
            "assignments": [],
            "unfilled": [],
            "completed": [],
            "failed": [],
            "consensus_output": None,
            "status": "running",
        }

        res = asyncio.run(form_team_node(state))
        assignments = res.get("assignments", [])
        assert len(assignments) == 1, f"Expected 1 assignment, got {len(assignments)}"

        selected_id = assignments[0]["agent_id"]
        selected_name = assignments[0]["agent_name"]

        print(f"form_team_node selected: {selected_name} (ID: {selected_id})")
        assert selected_id == "spec-finance-001", (
            f"Expected domain specialist 'spec-finance-001' to win, but '{selected_id}' ({selected_name}) was selected instead!"
        )
        print("PASS: form_team_node correctly preferred domain specialist (perf=0.0) over cross-domain agent (perf=1.0)!\n")

        # Test 2: handle_failures_node selection
        failure_state: OrchestratorState = {
            "task_run_id": "test-run-2",
            "request_text": "Need financial diligence",
            "context": {},
            "required": [],
            "assignments": [],
            "unfilled": [],
            "completed": [],
            "failed": [
                {
                    "domain": "finance",
                    "capability": "financial_diligence",
                    "subtask": "Retry financial analysis",
                    "agent_id": "failed-dummy-id",
                    "agent_name": "failed-agent",
                    "result": None,
                    "success": False,
                    "latency_ms": 0.0,
                    "retries": 0,
                }
            ],
            "consensus_output": None,
            "status": "running",
        }

        # Mock _invoke_single_assignment to avoid actual agent execution
        async def dummy_invoke(task_run_id, request_text, assignment, delay=0.0):
            from app.agents.base_agent import AgentResult
            return assignment, AgentResult(agent_name=assignment["agent_name"], success=True, output="Success", latency_ms=10.0)

        orig_invoke = graph_module._invoke_single_assignment
        graph_module._invoke_single_assignment = dummy_invoke

        try:
            fail_res = asyncio.run(handle_failures_node(failure_state))
            completed_retry = fail_res.get("completed", [])
            assert len(completed_retry) == 1, f"Expected 1 completed retry, got {len(completed_retry)}"
            retry_agent_id = completed_retry[0]["agent_id"]
            retry_agent_name = completed_retry[0]["agent_name"]

            print(f"handle_failures_node selected replacement: {retry_agent_name} (ID: {retry_agent_id})")
            assert retry_agent_id == "spec-finance-001", (
                f"Expected domain specialist 'spec-finance-001' to win in failure handler, but '{retry_agent_id}' was selected!"
            )
            print("PASS: handle_failures_node correctly preferred domain specialist (perf=0.0) over cross-domain agent (perf=1.0)!\n")

        finally:
            graph_module._invoke_single_assignment = orig_invoke

        # Test 3: generate_consensus_node error formatting test
        # Test LLM exception handling in generate_consensus_node
        from app.config import settings
        orig_key = settings.GROQ_API_KEY
        settings.GROQ_API_KEY = "gsk_test_mock_key_12345"

        async def mock_llm_fail(prompt, max_tokens=1000):
            raise RuntimeError("API Rate Limit Exceeded (HTTP 429)")

        import app.llm_client as llm_module
        orig_complete = llm_module.complete
        llm_module.complete = mock_llm_fail

        try:
            consensus_state: OrchestratorState = {
                "task_run_id": "test-run-3",
                "request_text": "Synthesize findings",
                "context": {},
                "required": [],
                "assignments": [],
                "unfilled": [],
                "completed": [
                    {
                        "domain": "finance",
                        "agent_name": "finance-agent",
                        "subtask": "Diligence",
                        "result": "Financials look solid.",
                        "success": True,
                        "latency_ms": 50.0,
                    }
                ],
                "failed": [],
                "consensus_output": None,
                "status": "running",
            }

            c_res = asyncio.run(generate_consensus_node(consensus_state))
            c_status = c_res.get("status")
            c_output = c_res.get("consensus_output", "")

            print("--- Consensus LLM Error Handling Output ---")
            print(f"Status: {c_status}")
            print(f"Header preview:\n{c_output[:200]}")
            print("-------------------------------------------\n")

            assert c_status == "completed_with_errors", f"Expected status 'completed_with_errors', got '{c_status}'"
            assert "[CONSENSUS SYNTHESIS FAILED - see error below]" in c_output, "Expected error header prefix in consensus_output"
            assert "API Rate Limit Exceeded" in c_output, "Expected error message in consensus_output"

            print("PASS: generate_consensus_node correctly formatted failure header and set status to 'completed_with_errors'!\n")

        finally:
            settings.GROQ_API_KEY = orig_key
            llm_module.complete = orig_complete

    finally:
        graph_module.SessionLocal = orig_session_local
        db.close()

    print("ALL AUDIT FIX VERIFICATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_specialist_vs_generalist()
