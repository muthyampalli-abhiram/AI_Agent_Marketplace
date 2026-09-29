from app.database import SessionLocal
from app.models import Agent

db = SessionLocal()
agents = db.query(Agent).all()
for a in agents:
    print(a.name, a.domain, a.capabilities)
print(f"\nTotal agents: {len(agents)}")
db.close()