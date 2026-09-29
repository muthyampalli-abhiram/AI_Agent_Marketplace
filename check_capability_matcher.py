import asyncio
from app.database import SessionLocal
from app.models import Agent
from app.orchestrator.capability_matcher import decompose_request, score_agent

from app.database import init_db
import seed_agents

async def main():
    init_db()
    seed_agents.seed_agents()
    required = await decompose_request("Analyze this company's acquisition opportunity.")
    print(f"Decomposed into {len(required)} items:")
    for item in required:
        print(f"- domain={item.get('domain')} capability={item.get('capability')} subtask={item.get('subtask')[:60]}")

    db = SessionLocal()
    finance_agent = db.query(Agent).filter(Agent.name == "finance-agent").first()
    legal_agent = db.query(Agent).filter(Agent.name == "legal-agent").first()

    print("\nScoring 'finance' capability against finance-agent:", score_agent("finance", finance_agent))
    print("Scoring 'finance' capability against legal-agent:", score_agent("finance", legal_agent))
    db.close()

asyncio.run(main())
