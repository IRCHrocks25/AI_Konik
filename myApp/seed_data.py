import re
from datetime import datetime

from django.utils import timezone as dj_tz
from django.utils.text import slugify

from .models import Agent, AgentPrompt, Event, Industry, Tool


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


# ── Industries ──────────────────────────────────────────────────────

INDUSTRY_SEEDS = [
    {"slug": "legal",         "name": "Legal",         "icon_class": "fa-scale-balanced", "sort_order": 100},
    {"slug": "healthcare",    "name": "Healthcare",    "icon_class": "fa-hospital",       "sort_order": 110},
    {"slug": "finance",       "name": "Finance",       "icon_class": "fa-sack-dollar",    "sort_order": 120},
    {"slug": "marketing",     "name": "Marketing",     "icon_class": "fa-bullhorn",       "sort_order": 130},
    {"slug": "technology",    "name": "Technology",    "icon_class": "fa-laptop-code",    "sort_order": 140},
    {"slug": "realestate",    "name": "Real Estate",   "icon_class": "fa-house",          "sort_order": 150},
    {"slug": "accounting",    "name": "Accounting",    "icon_class": "fa-chart-line",     "sort_order": 160},
    {"slug": "logistics",     "name": "Logistics",     "icon_class": "fa-truck",          "sort_order": 170},
    {"slug": "manufacturing", "name": "Manufacturing", "icon_class": "fa-gears",          "sort_order": 180},
]


def seed_industries():
    """Idempotent: get_or_create by slug. Returns count of newly-created rows."""
    created = 0
    for s in INDUSTRY_SEEDS:
        _, was_created = Industry.objects.get_or_create(
            slug=s["slug"],
            defaults={
                "name": s["name"],
                "icon_class": s["icon_class"],
                "sort_order": s["sort_order"],
                "is_active": True,
            },
        )
        if was_created:
            created += 1
    return created


# ── Events ──────────────────────────────────────────────────────────

EVENT_SEEDS = [
    {
        "title": "AI for Legal Teams: Contract Automation Workshop",
        "description": "Learn how to deploy AI contract review in your firm. Live demo with real NDA analysis and redline generation.",
        "date_str": "Apr 22, 2026",
        "time_str": "2:00 PM EST",
        "industry_slug": "legal",
        "is_featured": False,
    },
    {
        "title": "AI KONIK Summit 2026 — Annual Flagship Event",
        "description": "Two days of keynotes, workshops, and networking with 500+ SMB leaders pioneering AI adoption.",
        "date_str": "May 15–16, 2026",  # date range; parser takes the start
        "time_str": "9:00 AM EST",
        "industry_slug": None,  # source had industry='All'
        "is_featured": True,
    },
    {
        "title": "HIPAA-Compliant AI in Healthcare Practice",
        "description": "Navigate AI implementation in a HIPAA-regulated environment. Practical guidance from a healthcare compliance expert.",
        "date_str": "Apr 29, 2026",
        "time_str": "1:00 PM EST",
        "industry_slug": "healthcare",
        "is_featured": False,
    },
    {
        "title": "AI for CFOs: Finance Automation Masterclass",
        "description": "From automated financial reporting to AI-powered risk analysis — a hands-on session for finance leaders.",
        "date_str": "May 8, 2026",
        "time_str": "11:00 AM EST",
        "industry_slug": "finance",
        "is_featured": False,
    },
    {
        "title": "Content Marketing at Scale with AI Agents",
        "description": "Triple your content output without sacrificing quality. Live session building a content engine with AI agents.",
        "date_str": "May 3, 2026",
        "time_str": "3:00 PM EST",
        "industry_slug": "marketing",
        "is_featured": False,
    },
    {
        "title": "AI-Powered Technical Documentation Sprint",
        "description": "Build a complete docs-as-code pipeline with AI. From API specs to developer guides — automated end to end.",
        "date_str": "May 12, 2026",
        "time_str": "10:00 AM EST",
        "industry_slug": "technology",
        "is_featured": False,
    },
]


def _parse_event_datetime(date_str, time_str):
    """Parse 'Apr 22, 2026' + '2:00 PM EST' into a tz-aware datetime.

    Handles date ranges like 'May 15–16, 2026' by taking the start.
    Strips US tz abbreviations from the time component (we treat the
    parsed wall-clock as the project's TIME_ZONE via make_aware).
    Returns None if parsing fails.
    """
    if not date_str or not time_str:
        return None
    date_str = date_str.replace("–", "-").replace("—", "-")
    parts = date_str.rsplit(",", 1)
    if len(parts) != 2:
        return None
    date_main = parts[0].strip().split("-")[0].strip()
    year = parts[1].strip()
    normalized_date = f"{date_main}, {year}"
    time_clean = re.sub(
        r"\s*(EST|EDT|PST|PDT|UTC|GMT|CST|CDT|MST|MDT)\s*$",
        "",
        time_str.strip(),
        flags=re.IGNORECASE,
    )
    try:
        naive = datetime.strptime(f"{normalized_date} {time_clean}", "%b %d, %Y %I:%M %p")
    except ValueError:
        return None
    return dj_tz.make_aware(naive)


def seed_events():
    """Idempotent: get_or_create by slug. Returns count of newly-created rows.

    Note: source EVENTS array carries icon (FA markup) and bg (color/gradient)
    that the Event model doesn't store. Phase 9 cutover will decide whether to
    add icon_class/accent_bg fields or render via industry-level icons.
    """
    created = 0
    for s in EVENT_SEEDS:
        slug = slugify(s["title"])
        if not slug:
            continue
        event_dt = _parse_event_datetime(s["date_str"], s["time_str"])
        if event_dt is None:
            continue  # skip unparseable rows; do not raise
        industry = None
        if s.get("industry_slug"):
            industry = Industry.objects.filter(slug=s["industry_slug"]).first()
        _, was_created = Event.objects.get_or_create(
            slug=slug,
            defaults={
                "title": s["title"],
                "description": s["description"],
                "event_date": event_dt,
                "industry": industry,
                "is_featured": s.get("is_featured", False),
                "is_active": True,
            },
        )
        if was_created:
            created += 1
    return created


# ── Tools ───────────────────────────────────────────────────────────

TOOL_SEEDS = [
    {
        "name": "Claude (Anthropic)",
        "description": "The most capable AI assistant for legal, compliance, and complex reasoning tasks. Best-in-class for document analysis.",
        "icon_class": "fa-file-pen",
        "external_url": "https://claude.ai",
        "category": "Writing",
        "is_featured": True,
        "sort_order": 100,
    },
    {
        "name": "Perplexity AI",
        "description": "AI-powered research engine. Ideal for competitive intelligence, market research, and due diligence.",
        "icon_class": "fa-magnifying-glass",
        "external_url": "https://www.perplexity.ai",
        "category": "Research",
        "is_featured": False,
        "sort_order": 110,
    },
    {
        "name": "Midjourney",
        "description": "Best-in-class AI image generation. Used by marketing teams for brand visuals, ads, and creative content.",
        "icon_class": "fa-palette",
        "external_url": "https://www.midjourney.com",
        "category": "Design",
        "is_featured": False,
        "sort_order": 120,
    },
    {
        "name": "Notion AI",
        "description": "AI-powered workspace for teams. Excellent for SOPs, meeting notes, project documentation, and wikis.",
        "icon_class": "fa-chart-line",
        "external_url": "https://www.notion.so",
        "category": "Productivity",
        "is_featured": False,
        "sort_order": 130,
    },
    {
        "name": "HubSpot AI",
        "description": "AI-enhanced CRM for SMBs. Smart email generation, deal scoring, and automated follow-up sequences.",
        "icon_class": "fa-handshake",
        "external_url": "https://www.hubspot.com",
        "category": "CRM",
        "is_featured": False,
        "sort_order": 140,
    },
    {
        "name": "Descript",
        "description": "AI video editor with transcription, overdubbing, and automatic cut removal. Great for training and webinar content.",
        "icon_class": "fa-video",
        "external_url": "https://www.descript.com",
        "category": "Video",
        "is_featured": False,
        "sort_order": 150,
    },
]


def seed_tools():
    """Idempotent: get_or_create by slug. Returns count of newly-created rows."""
    created = 0
    for s in TOOL_SEEDS:
        slug = slugify(s["name"])
        if not slug:
            continue
        _, was_created = Tool.objects.get_or_create(
            slug=slug,
            defaults={
                "name": s["name"],
                "description": s["description"],
                "icon_class": s["icon_class"],
                "external_url": s["external_url"],
                "category": s["category"],
                "is_featured": s.get("is_featured", False),
                "is_active": True,
                "sort_order": s["sort_order"],
            },
        )
        if was_created:
            created += 1
    return created
