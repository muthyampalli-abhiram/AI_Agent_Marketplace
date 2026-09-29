import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.models import Agent
from app.orchestrator.capability_matcher import score_agent, canonical_domain

def run_verification():
    print("=== Testing Specialist vs Generalist Candidate Selection ===")

    # 1. Construct True Domain Specialist with low performance score (0.0)
    specialist = Agent(
        id="spec-1",
        name="finance-specialist",
        domain="finance",
        capabilities=["finance", "valuation", "dcf"],
        performance_score=0.0,
        status="active",
    )

    # 2. Construct Cross-Domain / Generalist Agent with high performance score (1.0)
    generalist = Agent(
        id="gen-1",
        name="market-generalist-with-finance-cap",
        domain="market",
        capabilities=["market", "finance", "strategy"],
        performance_score=1.0,
        status="active",
    )

    req_domain = "finance"
    capability = "finance"
    target_domain = canonical_domain(req_domain) or canonical_domain(capability)

    candidate_pool = [specialist, generalist]

    # Test candidate selection logic (used in form_team_node and handle_failures_node)
    matching_domain_agents = [
        a for a in candidate_pool
        if target_domain and canonical_domain(a.domain) == target_domain
    ]

    best_agent = None
    max_score = -1.0

    if matching_domain_agents:
        best_agent = max(
            matching_domain_agents,
            key=lambda a: (a.performance_score if a.performance_score is not None else 0.7)
        )
        max_score = score_agent(capability, best_agent, domain=req_domain)
    else:
        for agent in candidate_pool:
            s = score_agent(capability, agent, domain=req_domain)
            if s > max_score:
                max_score = s
                best_agent = agent

    spec_score = score_agent(capability, specialist, domain=req_domain)
    gen_score = score_agent(capability, generalist, domain=req_domain)

    print(f"Required Domain/Capability: {req_domain}/{capability}")
    print(f"Specialist ({specialist.name}): domain={specialist.domain}, perf_score={specialist.performance_score}, score_agent={spec_score}")
    print(f"Generalist ({generalist.name}): domain={generalist.domain}, perf_score={generalist.performance_score}, score_agent={gen_score}")
    print(f"Selected Winner: {best_agent.name} (score: {max_score})")

    assert spec_score > gen_score, f"Expected specialist score ({spec_score}) > generalist score ({gen_score})"
    assert best_agent.id == specialist.id, f"Expected specialist '{specialist.name}' to win, but '{best_agent.name}' won!"

    print("\nVERIFICATION SUCCESSFUL: Domain specialist (perf=0.0) outranked cross-domain generalist (perf=1.0)!")

if __name__ == "__main__":
    run_verification()
