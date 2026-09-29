from typing import List
from app.agents.base_agent import BaseAgent


class FinanceAgent(BaseAgent):
    name = "finance-agent"
    domain = "finance"
    capabilities = [
        "dcf_valuation",
        "financial_ratios",
        "deal_pricing",
        "synergy_estimation",
    ]
    system_prompt = (
        "You are an M&A Finance Analyst. You evaluate financial health, DCF valuation models, "
        "deal pricing structures, and synergy estimation."
    )


class LegalAgent(BaseAgent):
    name = "legal-agent"
    domain = "legal"
    capabilities = [
        "regulatory_review",
        "contract_risk",
        "antitrust",
        "ip_diligence",
    ]
    system_prompt = (
        "You are a Legal & Compliance Analyst. You review regulatory approval risks, "
        "contract liabilities, antitrust exposure, and intellectual property diligence."
    )


class MarketAgent(BaseAgent):
    name = "market-agent"
    domain = "market"
    capabilities = [
        "competitive_landscape",
        "market_sizing",
        "customer_overlap",
        "brand_fit",
    ]
    system_prompt = (
        "You are a Market Strategy Analyst. You examine market sizing, competitive dynamics, "
        "customer overlap, and strategic brand positioning."
    )


class TechnologyAgent(BaseAgent):
    name = "technology-agent"
    domain = "technology"
    capabilities = [
        "tech_stack_audit",
        "integration_complexity",
        "ip_and_patents",
        "security_posture",
    ]
    system_prompt = (
        "You are a Technology Due-Diligence Analyst. You audit tech stacks, evaluate integration complexity, "
        "patent quality, and cybersecurity posture."
    )


class HRAgent(BaseAgent):
    name = "hr-agent"
    domain = "hr"
    capabilities = [
        "culture_fit",
        "retention_risk",
        "org_design",
        "compensation_alignment",
    ]
    system_prompt = (
        "You are an HR & Organizational Analyst. You assess corporate culture compatibility, key talent "
        "retention risks, organizational structure, and compensation alignment."
    )


class RiskAgent(BaseAgent):
    name = "risk-agent"
    domain = "risk"
    capabilities = [
        "risk_aggregation",
        "scenario_analysis",
        "downside_modeling",
    ]
    system_prompt = (
        "You are a Chief Risk Analyst. You aggregate cross-functional deal risks, perform downside scenario "
        "modeling, and build prioritized risk registers."
    )


DOMAIN_AGENT_CLASSES: List[type[BaseAgent]] = [
    FinanceAgent,
    LegalAgent,
    MarketAgent,
    TechnologyAgent,
    HRAgent,
    RiskAgent,
]


def get_agent_instance(name: str) -> BaseAgent:
    """Instantiate and return an agent instance matching the given name."""
    for cls in DOMAIN_AGENT_CLASSES:
        if cls.name == name:
            return cls()
    raise ValueError(f"Unknown agent name: '{name}'")
