import asyncio
import json
import re
from typing import Any, Dict, List

from app import llm_client

from app.config import settings
from app.models import Agent

DEFAULT_TAXONOMY: Dict[str, List[str]] = {
    "finance": [
        "finance",
        "valuation",
        "dcf",
        "ratios",
        "pricing",
        "synergy",
        "cost",
        "financial",
        "accounting",
        "deal",
    ],
    "legal": [
        "legal",
        "contract",
        "regulatory",
        "compliance",
        "antitrust",
        "ip",
        "diligence",
        "liability",
        "law",
    ],
    "market": [
        "market",
        "competitor",
        "competitive",
        "sizing",
        "customer",
        "brand",
        "strategy",
        "commercial",
        "industry",
    ],
    "technology": [
        "technology",
        "tech",
        "stack",
        "code",
        "architecture",
        "security",
        "infrastructure",
        "software",
        "system",
    ],
    "hr": [
        "hr",
        "people",
        "culture",
        "retention",
        "org",
        "talent",
        "compensation",
        "workforce",
        "employee",
        "human",
        "organization",
    ],
    "risk": [
        "risk",
        "scenario",
        "downside",
        "threat",
        "mitigation",
        "register",
        "exposure",
        "vulnerability",
    ],
}

DOMAIN_SYNONYMS: Dict[str, set[str]] = {
    "finance": {
        "finance",
        "financial",
        "valuation",
        "dcf",
        "ratios",
        "pricing",
        "synergy",
        "cost",
        "accounting",
        "deal",
        "due_diligence",
        "financial_diligence",
    },
    "legal": {
        "legal",
        "contract",
        "regulatory",
        "compliance",
        "antitrust",
        "ip",
        "diligence",
        "liability",
        "law",
        "attorney",
        "regulatory_compliance",
    },
    "market": {
        "market",
        "competitor",
        "competitive",
        "sizing",
        "customer",
        "brand",
        "strategy",
        "commercial",
        "industry",
        "market_analysis",
        "market_position",
    },
    "technology": {
        "technology",
        "tech",
        "stack",
        "code",
        "architecture",
        "security",
        "infrastructure",
        "software",
        "system",
        "tech_stack",
        "product_roadmap",
    },
    "hr": {
        "hr",
        "people",
        "culture",
        "retention",
        "org",
        "talent",
        "compensation",
        "workforce",
        "employee",
        "human",
        "organization",
        "human_resources",
        "human_capital",
    },
    "risk": {
        "risk",
        "scenario",
        "downside",
        "threat",
        "mitigation",
        "register",
        "exposure",
        "vulnerability",
        "hazard",
        "contingency",
        "risk_assessment",
        "risk_management",
        "risk_identification",
    },
}


def canonical_domain(text: str) -> str:
    if not text:
        return ""
    raw = text.lower().strip()
    tokens = tokenize(raw)

    # 1. Direct match with canonical domain names
    for domain in DEFAULT_TAXONOMY.keys():
        if raw == domain or domain in tokens:
            return domain

    # 2. Match with domain synonyms or taxonomy keywords
    for domain, synonyms in DOMAIN_SYNONYMS.items():
        if raw in synonyms:
            return domain
        if tokens & synonyms:
            return domain
        if any(s in raw for s in synonyms if len(s) >= 4):
            return domain

    # 3. Check prefix match for 3+ letters
    for domain in DEFAULT_TAXONOMY.keys():
        if len(domain) >= 3 and any(
            t.startswith(domain[:3]) for t in tokens if len(t) >= 3
        ):
            return domain

    return ""


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


async def decompose_request(request_text: str) -> List[Dict[str, Any]]:
    """
    Decompose a user request into required specialist domains and subtasks.

    Uses LLM when available; falls back to default taxonomy decomposition.
    """
    api_key = settings.GROQ_API_KEY
    use_llm = (
        api_key
        and "your_" not in api_key
        and "placeholder" not in api_key
    )

    if use_llm:
        try:
            prompt = (
                f"Analyze the following user request: '{request_text}'\n\n"
                "Break this request into subtasks for ALL six specialist domains: "
                "finance, legal, market, technology, hr, risk (exactly one object per domain).\n"
                "Return ONLY a strict JSON array of 6 objects with keys 'domain', 'capability', and 'subtask'.\n"
                "Example format:\n"
                '[\n'
                '  {"domain": "finance", "capability": "financial_diligence", "subtask": "Analyze financial metrics"},\n'
                '  {"domain": "legal", "capability": "regulatory_compliance", "subtask": "Review legal contracts"},\n'
                '  {"domain": "market", "capability": "market_analysis", "subtask": "Assess market position"},\n'
                '  {"domain": "technology", "capability": "tech_stack_audit", "subtask": "Evaluate technology stack"},\n'
                '  {"domain": "hr", "capability": "workforce_eval", "subtask": "Assess human resources"},\n'
                '  {"domain": "risk", "capability": "risk_assessment", "subtask": "Identify potential risks"}\n'
                ']'
            )

            raw_text = await llm_client.complete(prompt, max_tokens=600)
            clean_text = _strip_markdown_fences(raw_text)
            parsed = json.loads(clean_text)
            if isinstance(parsed, list) and len(parsed) > 0:
                valid_domains = list(DEFAULT_TAXONOMY.keys())
                existing_domains = set()
                normalized_items = []
                for item in parsed:
                    d = (item.get("domain") or "").lower().strip()
                    cap = (item.get("capability") or "").lower().strip()
                    matched_domain = canonical_domain(d) or canonical_domain(cap)
                    if matched_domain and matched_domain in valid_domains:
                        item["domain"] = matched_domain
                        existing_domains.add(matched_domain)
                    else:
                        existing_domains.add(d)
                    normalized_items.append(item)

                for domain in valid_domains:
                    if domain not in existing_domains:
                        normalized_items.append(
                            {
                                "domain": domain,
                                "capability": domain,
                                "subtask": f"Provide a {domain} assessment relevant to: {request_text}",
                            }
                        )
                return normalized_items
        except Exception:
            pass

    # Keyword/Default fallback
    results = []
    for domain in DEFAULT_TAXONOMY.keys():
        results.append(
            {
                "domain": domain,
                "capability": domain,
                "subtask": f"Provide a {domain} assessment relevant to: {request_text}",
            }
        )
    return results


def tokenize(text: str) -> set[str]:
    if not text:
        return set()
    return set(re.split(r"[\s_]+", text.lower().strip()))


def score_agent(required_capability: str, agent: Agent, domain: str = "") -> float:
    """
    Score an agent against a required capability and domain (0.0 to 1.0).

    Weighted 70/30 in favor of capability/domain match over historical performance score.
    Domain specialists always receive priority over cross-domain capability keyword matches.
    Returns 0.0 immediately if agent is not active.
    """
    if not agent or agent.status != "active":
        return 0.0

    req_raw = (required_capability or "").lower().strip()
    dom_raw = (domain or "").lower().strip()
    agent_domain = canonical_domain(agent.domain or "")

    subtask_domain = canonical_domain(dom_raw) or canonical_domain(req_raw)

    match_score = 0.0

    if subtask_domain:
        if agent_domain == subtask_domain:
            # Primary domain specialist
            match_score = 1.0
        else:
            # Cross-domain candidate: cap match_score at 0.60 so domain specialist always outscores
            req_tokens = tokenize(req_raw)
            has_cap_overlap = False
            for cap in agent.capabilities or []:
                cap_tokens = tokenize(cap.lower())
                if req_raw == cap.lower() or (req_tokens & cap_tokens):
                    has_cap_overlap = True
                    break
            if has_cap_overlap:
                match_score = 0.40
            else:
                match_score = 0.0
    else:
        # Fallback keyword match when domain is completely ambiguous
        req_tokens = tokenize(req_raw)
        exact_cap_match = False
        token_cap_match = False

        for cap in agent.capabilities or []:
            cap_raw = cap.lower().strip()
            cap_tokens = tokenize(cap_raw)

            if req_raw == cap_raw:
                exact_cap_match = True
                break

            if req_tokens and cap_tokens and (req_tokens & cap_tokens):
                token_cap_match = True

        if exact_cap_match:
            match_score = 1.0
        elif token_cap_match:
            match_score = 0.85
        else:
            taxonomy_keywords = set(DEFAULT_TAXONOMY.get(agent_domain, []))
            if req_tokens & taxonomy_keywords:
                match_score = 0.80
            else:
                match_score = 0.0

    perf_score = agent.performance_score if agent.performance_score is not None else 0.7
    final_score = (0.7 * match_score) + (0.3 * perf_score)
    return round(final_score, 4)

