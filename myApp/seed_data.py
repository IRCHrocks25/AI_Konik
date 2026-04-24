from django.utils.text import slugify

from .models import Agent, AgentPrompt


AGENT_SEED_DATA = [
    {
        "name": "Contract Review Agent",
        "industry": "legal",
        "description": "Analyze contracts for risks, unfavorable clauses, and missing protections automatically.",
        "icon_class": "fa-scale-balanced",
        "accent_bg": "#EEF2FF",
        "tag": "M&A · Contracts",
        "usage_count": 12400,
        "is_featured": True,
        "sort_order": 1,
        "hints": [
            "Review this NDA for risks",
            "Explain Section 4.2 of this contract",
            "What clauses am I missing?",
            "Compare to industry standard terms",
        ],
        "use_cases": [
            "Review this NDA and highlight any clauses that could expose my company to unnecessary liability.",
            "Analyze the indemnification clauses in this software agreement and explain the risk in plain English.",
            "Compare these contract terms to standard industry practice and tell me what is unusual or missing.",
            "What are the key risks in this M&A term sheet that I should negotiate before signing?",
        ],
    },
    {
        "name": "Patient Communication Agent",
        "industry": "healthcare",
        "description": "Generate clear, empathetic patient communications and follow-up messages.",
        "icon_class": "fa-comments",
        "accent_bg": "#EEF2FF",
        "tag": "Patient Support",
        "usage_count": 7300,
        "is_featured": True,
        "sort_order": 2,
        "hints": [
            "Draft a patient-friendly follow-up message",
            "Rewrite this diagnosis in simple language",
            "Create discharge instructions for this case",
            "Generate a care reminder text message",
        ],
        "use_cases": [
            "Rewrite this clinical update in plain language a patient can understand.",
            "Draft a compassionate follow-up email after a telehealth appointment.",
            "Create clear discharge instructions for a patient with migraine symptoms.",
            "Generate a medication reminder message with simple next steps.",
        ],
    },
    {
        "name": "Risk Analysis Agent",
        "industry": "finance",
        "description": "Comprehensive financial risk assessment and portfolio analysis reports.",
        "icon_class": "fa-sack-dollar",
        "accent_bg": "#FFFBEB",
        "tag": "Risk & Reporting",
        "usage_count": 11200,
        "is_featured": True,
        "sort_order": 3,
        "hints": [
            "Analyze portfolio concentration risk",
            "Summarize key risks in this financial report",
            "Generate an investor update draft",
            "Flag compliance issues in this filing",
        ],
        "use_cases": [
            "Assess concentration risk across sectors in this portfolio.",
            "Summarize major financial risks from this quarterly report.",
            "Draft a concise investor performance update email.",
            "Identify potential red flags in this regulatory filing.",
        ],
    },
    {
        "name": "Content Strategy Agent",
        "industry": "marketing",
        "description": "Build complete content strategies with SEO-optimized briefs and editorial calendars.",
        "icon_class": "fa-bullhorn",
        "accent_bg": "#FFF1F2",
        "tag": "Content · SEO",
        "usage_count": 18500,
        "is_featured": True,
        "sort_order": 4,
        "hints": [
            "Build a 30-day content calendar",
            "Write 5 ad copy variants",
            "Create SEO blog outlines",
            "Rewrite copy for our brand voice",
        ],
        "use_cases": [
            "Create a campaign content calendar for the next 4 weeks.",
            "Draft high-converting ad copy for paid social.",
            "Generate SEO-friendly blog outlines around this keyword set.",
            "Rewrite this landing page to better match our brand tone.",
        ],
    },
    {
        "name": "Technical Documentation Agent",
        "industry": "technology",
        "description": "Generate API docs, developer guides, and technical specs from code and requirements.",
        "icon_class": "fa-laptop-code",
        "accent_bg": "#F0F9FF",
        "tag": "Docs & Engineering",
        "usage_count": 16300,
        "is_featured": True,
        "sort_order": 5,
        "hints": [
            "Document this API endpoint",
            "Review this code for security issues",
            "Create a rollout checklist",
            "Generate a technical spec draft",
        ],
        "use_cases": [
            "Write API documentation from this endpoint definition.",
            "Review this code snippet for security and performance concerns.",
            "Create a deployment checklist for this release.",
            "Draft a technical design spec from these requirements.",
        ],
    },
    {
        "name": "Property Analysis Agent",
        "industry": "realestate",
        "description": "Comprehensive property valuation, market analysis, and investment potential reports.",
        "icon_class": "fa-house",
        "accent_bg": "#F5F3FF",
        "tag": "Leasing & Valuation",
        "usage_count": 5400,
        "is_featured": False,
        "sort_order": 6,
        "hints": [
            "Analyze this property investment",
            "Review this lease for risks",
            "Estimate cash flow and cap rate",
            "Summarize neighborhood comps",
        ],
        "use_cases": [
            "Evaluate this property for investment return and risk.",
            "Review this lease and highlight unfavorable clauses.",
            "Estimate cap rate and monthly cash flow for this deal.",
            "Summarize local comparable properties and pricing trends.",
        ],
    },
    {
        "name": "Tax Preparation Agent",
        "industry": "accounting",
        "description": "Streamline tax prep with automated data extraction and filing guidance.",
        "icon_class": "fa-chart-line",
        "accent_bg": "#ECFDF5",
        "tag": "Tax & Audit",
        "usage_count": 7800,
        "is_featured": False,
        "sort_order": 7,
        "hints": [
            "Project year-end tax liability",
            "Prepare an audit checklist",
            "Summarize bookkeeping anomalies",
            "Draft client-ready financial notes",
        ],
        "use_cases": [
            "Project tax liability using these YTD numbers.",
            "Create an audit prep checklist for this client.",
            "Identify anomalies in this general ledger extract.",
            "Draft plain-language notes for this financial summary.",
        ],
    },
    {
        "name": "Supply Chain Agent",
        "industry": "logistics",
        "description": "Optimize supply chain operations with demand forecasting and vendor analysis.",
        "icon_class": "fa-truck",
        "accent_bg": "#FFF7ED",
        "tag": "Supply Chain",
        "usage_count": 6300,
        "is_featured": False,
        "sort_order": 8,
        "hints": [
            "Optimize this delivery route plan",
            "Identify supply chain bottlenecks",
            "Create a vendor performance summary",
            "Forecast inventory needs",
        ],
        "use_cases": [
            "Analyze this route plan and suggest efficiency improvements.",
            "Identify key bottlenecks in this supply chain workflow.",
            "Summarize vendor performance using these delivery KPIs.",
            "Forecast inventory requirements for next month.",
        ],
    },
    {
        "name": "QA Analysis Agent",
        "industry": "manufacturing",
        "description": "Automated quality control checklists, defect analysis, and compliance reporting.",
        "icon_class": "fa-gears",
        "accent_bg": "#F8FAFC",
        "tag": "Quality & Operations",
        "usage_count": 4800,
        "is_featured": False,
        "sort_order": 9,
        "hints": [
            "Create a quality control checklist",
            "Analyze production downtime causes",
            "Suggest process improvements",
            "Draft a maintenance schedule",
        ],
        "use_cases": [
            "Create a QA checklist for this production line.",
            "Analyze downtime logs and identify root causes.",
            "Suggest lean process improvements for this workflow.",
            "Draft a preventive maintenance schedule for this equipment.",
        ],
    },
]


def seed_agents_and_prompts():
    if Agent.objects.exists():
        return

    for agent_data in AGENT_SEED_DATA:
        hints = agent_data.get("hints", [])
        use_cases = agent_data.get("use_cases", [])
        agent = Agent.objects.create(
            name=agent_data["name"],
            slug=slugify(agent_data["name"]),
            industry=agent_data["industry"],
            description=agent_data["description"],
            icon_class=agent_data.get("icon_class", "fa-robot"),
            accent_bg=agent_data.get("accent_bg", "#EEF2FF"),
            tag=agent_data.get("tag", ""),
            usage_count=agent_data.get("usage_count", 0),
            is_featured=agent_data.get("is_featured", False),
            sort_order=agent_data.get("sort_order", 100),
        )
        AgentPrompt.objects.bulk_create(
            [
                *[
                    AgentPrompt(
                        agent=agent,
                        prompt_type="hint",
                        content=hint,
                        sort_order=index + 1,
                    )
                    for index, hint in enumerate(hints)
                ],
                *[
                    AgentPrompt(
                        agent=agent,
                        prompt_type="use_case",
                        content=use_case,
                        sort_order=index + 1,
                    )
                    for index, use_case in enumerate(use_cases)
                ],
            ]
        )
