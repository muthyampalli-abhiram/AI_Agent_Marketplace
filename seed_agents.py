from app.database import init_db, SessionLocal
from app.models import Agent

SEED_AGENTS = [
    {
        "name": "finance-agent",
        "domain": "finance",
        "capabilities": [
            "dcf_valuation",
            "financial_ratios",
            "deal_pricing",
            "synergy_estimation",
        ],
        "description": "M&A finance analyst: valuation, deal structure, financing feasibility, synergy estimation.",
    },
    {
        "name": "legal-agent",
        "domain": "legal",
        "capabilities": [
            "regulatory_review",
            "contract_risk",
            "antitrust",
            "ip_diligence",
        ],
        "description": "Legal & compliance analyst: regulatory approval risk, antitrust exposure, contract and IP diligence.",
    },
    {
        "name": "market-agent",
        "domain": "market",
        "capabilities": [
            "competitive_landscape",
            "market_sizing",
            "customer_overlap",
            "brand_fit",
        ],
        "description": "Market strategy analyst: competitive landscape, customer overlap, strategic fit.",
    },
    {
        "name": "technology-agent",
        "domain": "technology",
        "capabilities": [
            "tech_stack_audit",
            "integration_complexity",
            "ip_and_patents",
            "security_posture",
        ],
        "description": "Technology due-diligence analyst: tech stack, integration complexity, security posture.",
    },
    {
        "name": "hr-agent",
        "domain": "hr",
        "capabilities": [
            "culture_fit",
            "retention_risk",
            "org_design",
            "compensation_alignment",
        ],
        "description": "HR/people analyst: culture fit, retention risk, org design implications.",
    },
    {
        "name": "risk-agent",
        "domain": "risk",
        "capabilities": [
            "risk_aggregation",
            "scenario_analysis",
            "downside_modeling",
        ],
        "description": "Risk analyst: aggregates cross-functional risks into a prioritized risk register.",
    },
]


def seed_agents() -> None:
    init_db()
    db = SessionLocal()
    try:
        for agent_data in SEED_AGENTS:
            agent = db.query(Agent).filter(Agent.name == agent_data["name"]).first()
            if agent:
                agent.domain = agent_data["domain"]
                agent.capabilities = agent_data["capabilities"]
                agent.description = agent_data["description"]
                action = "Updated"
            else:
                agent = Agent(
                    name=agent_data["name"],
                    domain=agent_data["domain"],
                    capabilities=agent_data["capabilities"],
                    description=agent_data["description"],
                )
                db.add(agent)
                action = "Inserted"
            db.commit()
            db.refresh(agent)
            print(f"[{action}] Agent: {agent.name} (id: {agent.id}, domain: {agent.domain})")
    finally:
        db.close()


if __name__ == "__main__":
    seed_agents()
