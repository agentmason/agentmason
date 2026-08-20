"""Seed script — provisions a complete dogfood business workspace.

Populates:
  • BusinessConfig (tenant profile)
  • Business Memory (using existing MemoryService)
  • Business Graph (using existing GraphService)
  • Specialized Agents (using existing SpecializedAgentRegistry)
  • KPIs (demo data)
  • Inbox items (demo data)
  • Agent activities (demo data)
  • Business metrics (demo data)

Every synthetic record is marked `is_demo_data = True`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from packages.dogfood.models import (
    BusinessConfig, BusinessKPI, BusinessInboxItem,
    AgentActivity, BusinessMetric,
)
from packages.memory.service import MemoryService
from packages.graph.service import GraphService

logger = logging.getLogger(__name__)


# ╭──────────────────────────────────────────────────────────────────────╮
# │                      DEFAULT BUSINESS PROFILE                       │
# ╰──────────────────────────────────────────────────────────────────────╯

DEFAULT_BUSINESS = dict(
    company_name="Tech Burner Corporation",
    product_name="AgentMason",
    business_type="AI Software / SaaS",
    tagline="AI Agents That Deliver",
    departments=[
        "Executive", "Sales", "Marketing", "Finance",
        "Operations", "Product", "Engineering",
        "Customer Success", "Government Contracts",
    ],
    business_activities=[
        "Software development",
        "AI product development",
        "Customer acquisition",
        "Marketing",
        "Sales",
        "Government contracting",
        "Business administration",
    ],
    goals=[
        {"name": "Revenue Growth", "description": "Increase monthly recurring revenue", "category": "revenue"},
        {"name": "Customer Acquisition", "description": "Acquire new AgentMason customers", "category": "sales"},
        {"name": "Product Adoption", "description": "Increase AgentMason adoption and usage", "category": "product"},
        {"name": "Operations Efficiency", "description": "Automate repetitive administrative work", "category": "operations"},
        {"name": "Government Expansion", "description": "Identify and pursue relevant government opportunities", "category": "government"},
        {"name": "Engineering Velocity", "description": "Improve development velocity and quality", "category": "engineering"},
    ],
    kpis=[
        {"name": "Monthly Recurring Revenue", "unit": "$", "target": 100000, "category": "revenue"},
        {"name": "New Customers", "unit": "count", "target": 10, "category": "sales"},
        {"name": "Active Customers", "unit": "count", "target": 50, "category": "sales"},
        {"name": "Customer Acquisition Cost", "unit": "$", "target": 2000, "category": "sales"},
        {"name": "Pipeline Value", "unit": "$", "target": 500000, "category": "sales"},
        {"name": "Open Leads", "unit": "count", "target": 30, "category": "sales"},
        {"name": "Conversion Rate", "unit": "%", "target": 15, "category": "sales"},
        {"name": "Outstanding Invoices", "unit": "$", "target": 0, "category": "finance"},
        {"name": "Monthly Expenses", "unit": "$", "target": 50000, "category": "finance"},
        {"name": "Operating Margin", "unit": "%", "target": 30, "category": "finance"},
        {"name": "Product Usage", "unit": "sessions", "target": 1000, "category": "product"},
        {"name": "Workflow Automation Rate", "unit": "%", "target": 60, "category": "operations"},
        {"name": "Human Intervention Rate", "unit": "%", "target": 20, "category": "operations"},
        {"name": "Government Opportunities", "unit": "count", "target": 5, "category": "government"},
        {"name": "Proposal Pipeline", "unit": "count", "target": 3, "category": "government"},
    ],
    demo_mode=True,
)


# ╭──────────────────────────────────────────────────────────────────────╮
# │                         BUSINESS MEMORIES                           │
# ╰──────────────────────────────────────────────────────────────────────╯

SEED_MEMORIES = [
    # Business facts
    {"category": "business_fact", "title": "Primary Product",
     "content": "AgentMason is the company's primary AI product — an enterprise AI agent platform that designs, builds, and orchestrates business delivery."},
    {"category": "business_fact", "title": "Target Market",
     "content": "The company targets small and medium-sized businesses that need AI-driven automation for daily operations."},
    {"category": "business_fact", "title": "Company Type",
     "content": "Tech Burner Corporation is an AI Software / SaaS company specializing in agentic AI for business operations."},
    {"category": "business_fact", "title": "Government Interest",
     "content": "The company is exploring government contracting opportunities, specifically in AI/ML services and data analytics for federal and state agencies."},

    # Business rules
    {"category": "business_rule", "title": "External Communication Approval",
     "content": "All external communications (emails to customers, prospects, or partners) require human approval before sending."},
    {"category": "business_rule", "title": "Financial Transaction Approval",
     "content": "Financial transactions and payments require explicit human approval. AgentMason may recommend but never autonomously execute financial actions."},
    {"category": "business_rule", "title": "Government Submission Review",
     "content": "Government submissions, proposals, and compliance documents require mandatory human review before submission. No autonomous government filings."},
    {"category": "business_rule", "title": "Communication Tone",
     "content": "Customer communication should be professional, concise, and personalized. Avoid generic templates."},

    # Preferences
    {"category": "preference", "title": "Communication Style",
     "content": "Prefer concise, data-driven communications. Lead with insights and recommendations, not lengthy introductions."},
    {"category": "preference", "title": "Analysis Approach",
     "content": "When analyzing business data, always provide evidence and sources. Never present fabricated data as real."},

    # Goals
    {"category": "goal", "title": "Revenue Target",
     "content": "Achieve $100,000 in monthly recurring revenue within the next 6 months."},
    {"category": "goal", "title": "Customer Growth",
     "content": "Acquire 10 new paying customers per month through direct sales and marketing."},
    {"category": "goal", "title": "Government Pipeline",
     "content": "Build a pipeline of at least 5 active government contract opportunities."},

    # Processes
    {"category": "process", "title": "Lead Qualification Process",
     "content": "Step 1: Research the lead's company. Step 2: Determine if they match our target customer profile (SMB, needs automation). Step 3: Score the opportunity (1-10). Step 4: Create personalized outreach draft. Step 5: Get approval before sending."},
    {"category": "process", "title": "Invoice Follow-Up Process",
     "content": "When an invoice is overdue: Day 1-7: Send friendly reminder. Day 8-14: Escalate to account manager. Day 15+: Flag for executive review."},
]


# ╭──────────────────────────────────────────────────────────────────────╮
# │                        BUSINESS GRAPH                               │
# ╰──────────────────────────────────────────────────────────────────────╯

SEED_ENTITIES = [
    # Company
    {"entity_type": "company", "name": "Tech Burner Corporation",
     "description": "AI Software / SaaS company — creator of AgentMason",
     "properties": {"industry": "AI Software", "founded": "2024", "type": "SaaS"}},
    # Product
    {"entity_type": "product", "name": "AgentMason",
     "description": "Enterprise AI agent platform that designs, builds, and orchestrates business delivery",
     "properties": {"type": "SaaS Platform", "status": "Active"}},
    # Departments
    {"entity_type": "department", "name": "Executive", "description": "Strategic leadership and business oversight"},
    {"entity_type": "department", "name": "Sales", "description": "Revenue generation, lead management, customer acquisition"},
    {"entity_type": "department", "name": "Marketing", "description": "Brand awareness, content, campaigns, lead generation"},
    {"entity_type": "department", "name": "Finance", "description": "Financial management, invoicing, expense tracking"},
    {"entity_type": "department", "name": "Operations", "description": "Process management, automation, vendor operations"},
    {"entity_type": "department", "name": "Product", "description": "Product strategy, feature prioritization, customer feedback"},
    {"entity_type": "department", "name": "Engineering", "description": "Software development, infrastructure, quality assurance"},
    {"entity_type": "department", "name": "Customer Success", "description": "Customer retention, onboarding, support"},
    {"entity_type": "department", "name": "Government Contracts", "description": "Government opportunity identification, proposal preparation, compliance"},
    # Goals
    {"entity_type": "goal", "name": "Revenue Growth", "description": "Increase monthly recurring revenue to $100K",
     "properties": {"target": "$100,000/mo", "timeframe": "6 months"}},
    {"entity_type": "goal", "name": "Customer Acquisition", "description": "Acquire 10 new customers per month",
     "properties": {"target": "10/month"}},
    {"entity_type": "goal", "name": "Government Expansion", "description": "Build government contract pipeline",
     "properties": {"target": "5 active opportunities"}},
    # Demo Customers
    {"entity_type": "customer", "name": "Acme Corporation",
     "description": "Mid-size manufacturing company, current customer",
     "properties": {"industry": "Manufacturing", "mrr": "$2,500", "status": "active", "is_demo": True}},
    {"entity_type": "customer", "name": "Pinnacle Consulting Group",
     "description": "Management consulting firm, current customer",
     "properties": {"industry": "Consulting", "mrr": "$1,800", "status": "active", "is_demo": True}},
    {"entity_type": "customer", "name": "Greenfield Analytics",
     "description": "Data analytics startup, recent customer",
     "properties": {"industry": "Analytics", "mrr": "$3,200", "status": "active", "is_demo": True}},
    # Demo Leads
    {"entity_type": "person", "name": "Sarah Chen",
     "description": "VP of Operations at NovaTech Industries — high-value lead",
     "properties": {"company": "NovaTech Industries", "role": "VP Operations", "score": 8, "status": "contacted", "is_demo": True}},
    {"entity_type": "person", "name": "Marcus Williams",
     "description": "CTO at DataBridge Solutions — qualified lead",
     "properties": {"company": "DataBridge Solutions", "role": "CTO", "score": 7, "status": "new", "is_demo": True}},
    {"entity_type": "person", "name": "Jennifer Park",
     "description": "Director of IT at MidWest Health Systems — new lead",
     "properties": {"company": "MidWest Health Systems", "role": "Director IT", "score": 6, "status": "new", "is_demo": True}},
    {"entity_type": "person", "name": "David Okafor",
     "description": "CEO of OkaFor Logistics — follow-up overdue",
     "properties": {"company": "OkaFor Logistics", "role": "CEO", "score": 9, "status": "follow_up_overdue", "is_demo": True}},
    # Demo Vendors
    {"entity_type": "vendor", "name": "CloudScale Hosting",
     "description": "Cloud infrastructure provider",
     "properties": {"service": "Cloud Hosting", "monthly_cost": "$4,200", "is_demo": True}},
    {"entity_type": "vendor", "name": "SecureAuth Pro",
     "description": "Authentication and security provider",
     "properties": {"service": "Auth/Security", "monthly_cost": "$890", "is_demo": True}},
    # Demo Government Opportunities
    {"entity_type": "contract", "name": "DOD-AI-2026-0847",
     "description": "Department of Defense — AI/ML Data Analytics Platform",
     "properties": {"agency": "Department of Defense", "value": "$2.4M", "deadline": "2026-09-15", "status": "open", "is_demo": True}},
    {"entity_type": "contract", "name": "GSA-IT-2026-1203",
     "description": "GSA — IT Modernization AI Tools",
     "properties": {"agency": "GSA", "value": "$850K", "deadline": "2026-09-01", "status": "open", "is_demo": True}},
    {"entity_type": "contract", "name": "VA-HEALTH-2026-0392",
     "description": "VA — Healthcare Data Processing Automation",
     "properties": {"agency": "Veterans Affairs", "value": "$1.2M", "deadline": "2026-10-30", "status": "open", "is_demo": True}},
]

# (source_name, target_name, relationship_type, properties)
SEED_RELATIONSHIPS = [
    ("Tech Burner Corporation", "AgentMason", "owns", {}),
    ("Tech Burner Corporation", "Executive", "has_department", {}),
    ("Tech Burner Corporation", "Sales", "has_department", {}),
    ("Tech Burner Corporation", "Marketing", "has_department", {}),
    ("Tech Burner Corporation", "Finance", "has_department", {}),
    ("Tech Burner Corporation", "Operations", "has_department", {}),
    ("Tech Burner Corporation", "Product", "has_department", {}),
    ("Tech Burner Corporation", "Engineering", "has_department", {}),
    ("Tech Burner Corporation", "Customer Success", "has_department", {}),
    ("Tech Burner Corporation", "Government Contracts", "has_department", {}),
    ("Tech Burner Corporation", "Revenue Growth", "has_goal", {}),
    ("Tech Burner Corporation", "Customer Acquisition", "has_goal", {}),
    ("Tech Burner Corporation", "Government Expansion", "has_goal", {}),
    # Customer relationships
    ("Acme Corporation", "AgentMason", "uses", {"since": "2026-03"}),
    ("Pinnacle Consulting Group", "AgentMason", "uses", {"since": "2026-05"}),
    ("Greenfield Analytics", "AgentMason", "uses", {"since": "2026-07"}),
    # Lead relationships
    ("Sarah Chen", "Sales", "lead_for", {}),
    ("Marcus Williams", "Sales", "lead_for", {}),
    ("Jennifer Park", "Sales", "lead_for", {}),
    ("David Okafor", "Sales", "lead_for", {}),
    # Vendor relationships
    ("Tech Burner Corporation", "CloudScale Hosting", "contracts_with", {}),
    ("Tech Burner Corporation", "SecureAuth Pro", "contracts_with", {}),
    # Government opportunity relationships
    ("Government Contracts", "DOD-AI-2026-0847", "tracks", {}),
    ("Government Contracts", "GSA-IT-2026-1203", "tracks", {}),
    ("Government Contracts", "VA-HEALTH-2026-0392", "tracks", {}),
    # Department-goal links
    ("Sales", "Revenue Growth", "contributes_to", {}),
    ("Sales", "Customer Acquisition", "contributes_to", {}),
    ("Marketing", "Customer Acquisition", "contributes_to", {}),
    ("Government Contracts", "Government Expansion", "contributes_to", {}),
    ("Engineering", "AgentMason", "develops", {}),
    ("Product", "AgentMason", "manages", {}),
]


# ╭──────────────────────────────────────────────────────────────────────╮
# │                    DEMO SPECIALIZED AGENTS                          │
# ╰──────────────────────────────────────────────────────────────────────╯

SEED_AGENTS = [
    {
        "name": "Executive Agent",
        "agent_type": "executive",
        "description": "Provides business overview, KPI analysis, strategic recommendations, risk identification, and priority management.",
        "capabilities": ["business_overview", "kpi_analysis", "strategic_recommendation", "risk_identification", "priority_management"],
        "allowed_tools": ["text_analysis", "business_memory", "business_graph", "calculator"],
        "allowed_data_sources": ["business_memory", "business_graph", "kpis", "inbox"],
        "supported_tasks": ["business_review", "executive_briefing", "risk_assessment", "priority_ranking", "strategic_planning"],
        "system_prompt": "You are the Executive Agent for AgentMason. Your role is to provide high-level business analysis, identify priorities, assess risks, and recommend strategic actions. Always cite evidence and data sources. Be concise and action-oriented.",
        "risk_level": "medium",
    },
    {
        "name": "Sales Agent",
        "agent_type": "sales",
        "description": "Handles lead research, qualification, follow-ups, pipeline analysis, and customer opportunity identification.",
        "capabilities": ["lead_research", "lead_qualification", "customer_analysis", "pipeline_analysis", "follow_up_management", "sales_analysis"],
        "allowed_tools": ["text_analysis", "business_memory", "business_graph"],
        "allowed_data_sources": ["business_memory", "business_graph", "crm"],
        "supported_tasks": ["lead_analysis", "customer_risk_analysis", "pipeline_review", "prospect_research", "follow_up_recommendations"],
        "system_prompt": "You are the Sales Agent for AgentMason. Research leads, qualify prospects, analyze the pipeline, and draft personalized follow-up communications. All external communications require human approval. Score leads 1-10 based on fit with target market (SMBs needing AI automation).",
        "risk_level": "medium",
    },
    {
        "name": "Marketing Agent",
        "agent_type": "marketing",
        "description": "Generates content ideas, analyzes campaigns, supports lead generation, drafts social content, and reviews marketing performance.",
        "capabilities": ["content_generation", "campaign_analysis", "lead_generation", "social_content", "marketing_analytics"],
        "allowed_tools": ["text_analysis", "business_memory", "business_graph"],
        "allowed_data_sources": ["business_memory", "business_graph", "marketing_data"],
        "supported_tasks": ["content_ideation", "campaign_review", "social_post_draft", "marketing_performance", "lead_gen_strategy"],
        "system_prompt": "You are the Marketing Agent for AgentMason. Create content ideas, analyze campaigns, suggest LinkedIn posts, identify potential customers, and recommend marketing actions. All generated external content must be clearly marked as AI-generated drafts until approved.",
        "risk_level": "low",
    },
    {
        "name": "Finance Agent",
        "agent_type": "finance",
        "description": "Analyzes expenses, tracks invoices, reviews revenue, provides cash-flow insights, and identifies savings opportunities.",
        "capabilities": ["expense_analysis", "invoice_tracking", "revenue_analysis", "cash_flow_analysis", "financial_forecasting", "cost_optimization"],
        "allowed_tools": ["calculator", "text_analysis", "business_memory", "business_graph"],
        "allowed_data_sources": ["business_memory", "business_graph", "financial_data"],
        "supported_tasks": ["expense_analysis", "invoice_analysis", "cost_optimization", "financial_impact", "budget_review"],
        "system_prompt": "You are the Finance Agent for AgentMason. Analyze expenses, track invoices, review revenue trends, identify potential savings, and provide cash-flow insights. NEVER autonomously execute financial transactions. All financial actions require explicit human approval. Clearly distinguish between actual data and estimates.",
        "risk_level": "high",
    },
    {
        "name": "Operations Agent",
        "agent_type": "operations",
        "description": "Manages tasks, automates processes, handles vendor operations, and coordinates administrative workflows.",
        "capabilities": ["task_management", "process_automation", "vendor_operations", "administrative_workflows", "business_process_analysis", "process_optimization"],
        "allowed_tools": ["text_analysis", "business_memory", "business_graph"],
        "allowed_data_sources": ["business_memory", "business_graph", "operational_data"],
        "supported_tasks": ["process_analysis", "bottleneck_identification", "metrics_analysis", "process_improvement", "task_prioritization"],
        "system_prompt": "You are the Operations Agent for AgentMason. Manage tasks, identify process improvements, coordinate vendor relationships, and automate administrative work. Focus on measurable efficiency gains.",
        "risk_level": "medium",
    },
    {
        "name": "Product Agent",
        "agent_type": "product",
        "description": "Analyzes customer feedback, tracks feature requests, manages product priorities, and reviews product analytics.",
        "capabilities": ["feedback_analysis", "feature_prioritization", "product_analytics", "customer_insights", "roadmap_planning"],
        "allowed_tools": ["text_analysis", "business_memory", "business_graph"],
        "allowed_data_sources": ["business_memory", "business_graph", "product_data"],
        "supported_tasks": ["feedback_review", "feature_ranking", "usage_analysis", "product_health", "roadmap_recommendation"],
        "system_prompt": "You are the Product Agent for AgentMason. Analyze customer feedback, prioritize feature requests, review product usage patterns, and recommend product improvements. Ground recommendations in data.",
        "risk_level": "low",
    },
    {
        "name": "Engineering Agent",
        "agent_type": "engineering",
        "description": "Monitors engineering metrics, GitHub activity, project tracking, release readiness, and quality analysis.",
        "capabilities": ["engineering_metrics", "code_analysis", "release_assessment", "quality_analysis", "sprint_tracking"],
        "allowed_tools": ["text_analysis", "business_memory", "business_graph"],
        "allowed_data_sources": ["business_memory", "business_graph", "github", "jira"],
        "supported_tasks": ["engineering_health", "release_risk", "quality_review", "blocked_work", "sprint_analysis"],
        "system_prompt": "You are the Engineering Agent for AgentMason. Monitor engineering health, assess release readiness, identify quality risks, and track development velocity. If no connected engineering data sources are available, state clearly: 'No connected engineering data available.' Do not fabricate metrics.",
        "risk_level": "low",
    },
    {
        "name": "Government Contracts Agent",
        "agent_type": "government",
        "description": "Finds relevant government opportunities, analyzes solicitations, extracts requirements, tracks deadlines, creates compliance checklists, and prepares proposal drafts.",
        "capabilities": ["opportunity_discovery", "solicitation_analysis", "requirement_extraction", "deadline_tracking", "compliance_review", "proposal_preparation"],
        "allowed_tools": ["text_analysis", "business_memory", "business_graph"],
        "allowed_data_sources": ["business_memory", "business_graph", "sam_gov", "government_data"],
        "supported_tasks": ["find_opportunities", "analyze_solicitation", "extract_requirements", "bid_no_bid", "compliance_checklist", "proposal_draft"],
        "system_prompt": "You are the Government Contracts Agent for AgentMason. Find relevant government opportunities, analyze solicitations, extract requirements, compare company capabilities, identify gaps, create compliance checklists, and recommend bid/no-bid decisions. ALL government submissions require human approval. Never submit anything automatically.",
        "risk_level": "high",
    },
    {
        "name": "Customer Success Agent",
        "agent_type": "customer_success",
        "description": "Identifies customers needing attention, tracks engagement, monitors renewals, and recommends retention actions.",
        "capabilities": ["engagement_monitoring", "renewal_tracking", "churn_prevention", "onboarding_support", "satisfaction_analysis"],
        "allowed_tools": ["text_analysis", "business_memory", "business_graph"],
        "allowed_data_sources": ["business_memory", "business_graph", "crm"],
        "supported_tasks": ["customer_health", "engagement_review", "renewal_preparation", "at_risk_identification", "follow_up_prioritization"],
        "system_prompt": "You are the Customer Success Agent for AgentMason. Monitor customer engagement, identify at-risk accounts, track renewals, and recommend retention actions. External communications require approval.",
        "risk_level": "medium",
    },
]


# ╭──────────────────────────────────────────────────────────────────────╮
# │                     DEMO KPI DATA                                   │
# ╰──────────────────────────────────────────────────────────────────────╯

SEED_KPIS = [
    {"name": "Monthly Recurring Revenue", "category": "revenue", "value": 52400, "unit": "$", "target": 100000, "trend": "up"},
    {"name": "New Customers", "category": "sales", "value": 4, "unit": "count", "target": 10, "trend": "up"},
    {"name": "Active Customers", "category": "sales", "value": 23, "unit": "count", "target": 50, "trend": "up"},
    {"name": "Customer Acquisition Cost", "category": "sales", "value": 3200, "unit": "$", "target": 2000, "trend": "down"},
    {"name": "Pipeline Value", "category": "sales", "value": 287000, "unit": "$", "target": 500000, "trend": "up"},
    {"name": "Open Leads", "category": "sales", "value": 18, "unit": "count", "target": 30, "trend": "flat"},
    {"name": "Conversion Rate", "category": "sales", "value": 12.5, "unit": "%", "target": 15, "trend": "up"},
    {"name": "Outstanding Invoices", "category": "finance", "value": 14200, "unit": "$", "target": 0, "trend": "up"},
    {"name": "Monthly Expenses", "category": "finance", "value": 41800, "unit": "$", "target": 50000, "trend": "flat"},
    {"name": "Operating Margin", "category": "finance", "value": 20.2, "unit": "%", "target": 30, "trend": "up"},
    {"name": "Product Usage", "category": "product", "value": 642, "unit": "sessions", "target": 1000, "trend": "up"},
    {"name": "Workflow Automation Rate", "category": "operations", "value": 38, "unit": "%", "target": 60, "trend": "up"},
    {"name": "Human Intervention Rate", "category": "operations", "value": 34, "unit": "%", "target": 20, "trend": "down"},
    {"name": "Government Opportunities", "category": "government", "value": 3, "unit": "count", "target": 5, "trend": "up"},
    {"name": "Proposal Pipeline", "category": "government", "value": 1, "unit": "count", "target": 3, "trend": "flat"},
]


# ╭──────────────────────────────────────────────────────────────────────╮
# │                     DEMO INBOX ITEMS                                │
# ╰──────────────────────────────────────────────────────────────────────╯

SEED_INBOX = [
    {
        "category": "needs_attention",
        "priority": "critical",
        "title": "3 overdue customer follow-ups",
        "description": "Three customers have not received a follow-up within the expected timeframe.",
        "evidence": "David Okafor (OkaFor Logistics) — last contact 8 days ago. Acme Corporation — renewal discussion pending 5 days. Pinnacle Consulting — support ticket open 4 days.",
        "recommended_action": "Prioritize David Okafor follow-up (highest lead score: 9). Draft personalized messages for each.",
        "risk": "Potential churn and lost revenue if not addressed within 48 hours.",
        "why_it_matters": "These three accounts represent $6,800/month in combined MRR.",
        "agent_name": "Sales Agent",
        "data_sources": ["Business Graph", "Business Memory"],
        "requires_approval": True,
    },
    {
        "category": "needs_attention",
        "priority": "high",
        "title": "2 invoices require attention",
        "description": "Two invoices are past due and need follow-up.",
        "evidence": "Invoice #INV-2026-0089 — Acme Corp — $2,500 — 12 days overdue. Invoice #INV-2026-0092 — Pinnacle — $1,800 — 7 days overdue.",
        "recommended_action": "Send friendly payment reminder to Acme Corp (escalation threshold approaching). Send first reminder to Pinnacle.",
        "risk": "Combined $4,300 at risk. Acme approaching escalation threshold (14 days).",
        "why_it_matters": "Overdue invoices directly impact cash flow and operating margin.",
        "agent_name": "Finance Agent",
        "data_sources": ["Business Memory", "Financial Data (Demo)"],
        "requires_approval": True,
    },
    {
        "category": "opportunity",
        "priority": "high",
        "title": "Government opportunity deadline approaching",
        "description": "GSA-IT-2026-1203 (IT Modernization AI Tools) closes September 1, 2026.",
        "evidence": "Solicitation matches AgentMason capabilities: AI/ML tools, automation platforms, SaaS delivery. Estimated value: $850K.",
        "recommended_action": "Complete bid/no-bid analysis. If bid: begin compliance checklist and proposal outline.",
        "risk": "Only 13 days remaining. Proposal preparation typically requires 10-15 business days.",
        "why_it_matters": "This opportunity closely matches our product capabilities and could generate $850K in revenue.",
        "agent_name": "Government Contracts Agent",
        "data_sources": ["Business Graph", "Government Data (Demo)"],
        "requires_approval": True,
    },
    {
        "category": "needs_attention",
        "priority": "medium",
        "title": "4 leads have not been contacted",
        "description": "Four leads in the pipeline have not received initial outreach.",
        "evidence": "Marcus Williams (DataBridge Solutions, score: 7) — new lead, no contact. Jennifer Park (MidWest Health, score: 6) — new lead, no contact. Plus 2 additional lower-scored leads.",
        "recommended_action": "Research and qualify Marcus Williams first (highest score). Prepare personalized outreach for top leads.",
        "risk": "Leads go cold after 5-7 days without contact. Potential $15K+ MRR at stake.",
        "why_it_matters": "Converting even 2 of these leads would contribute significantly to monthly customer acquisition goal.",
        "agent_name": "Sales Agent",
        "data_sources": ["Business Graph", "Business Memory"],
        "requires_approval": False,
    },
    {
        "category": "opportunity",
        "priority": "medium",
        "title": "Potential cost savings identified",
        "description": "Analysis of recurring expenses identified potential savings of $1,240/month.",
        "evidence": "CloudScale Hosting: Current plan $4,200/mo — usage analysis suggests $3,400/mo plan sufficient (save $800). SecureAuth Pro: Duplicate license detected — potential save $440/mo.",
        "recommended_action": "Review hosting usage data. Contact CloudScale about plan downgrade. Audit SecureAuth licenses.",
        "risk": "Low — savings can be achieved without service disruption.",
        "why_it_matters": "Reducing expenses by $1,240/month improves operating margin by ~3 percentage points.",
        "agent_name": "Finance Agent",
        "data_sources": ["Business Graph", "Financial Data (Demo)"],
        "requires_approval": False,
    },
    {
        "category": "risk",
        "priority": "medium",
        "title": "Customer engagement declining — Greenfield Analytics",
        "description": "Greenfield Analytics product usage dropped 40% over the past 2 weeks.",
        "evidence": "Sessions decreased from 85/week to 52/week. No support tickets filed. No feature requests. Last login by primary user: 5 days ago.",
        "recommended_action": "Schedule check-in call with Greenfield Analytics primary contact. Review their onboarding completion status.",
        "risk": "Medium churn risk. $3,200/month MRR at stake.",
        "why_it_matters": "Greenfield is the highest-MRR customer. Losing them would reduce revenue by 6%.",
        "agent_name": "Customer Success Agent",
        "data_sources": ["Product Data (Demo)", "Business Graph"],
        "requires_approval": False,
    },
    {
        "category": "completed",
        "priority": "low",
        "title": "Monthly business review completed",
        "description": "AgentMason completed the automated monthly business review.",
        "evidence": "Reviewed: 15 KPIs, 23 active customers, 18 open leads, 3 government opportunities, 2 vendor contracts.",
        "recommended_action": "Review executive briefing for detailed findings.",
        "agent_name": "Executive Agent",
        "data_sources": ["Business Memory", "Business Graph", "KPI Data (Demo)"],
    },
    {
        "category": "information",
        "priority": "low",
        "title": "DOD opportunity matches company capabilities",
        "description": "DOD-AI-2026-0847 (AI/ML Data Analytics Platform) has strong alignment with AgentMason's capabilities.",
        "evidence": "Requirements match: AI/ML platform (✓), data analytics (✓), SaaS delivery (✓), FedRAMP path (partial). Estimated value: $2.4M. Deadline: September 15, 2026.",
        "recommended_action": "Add to active opportunity tracking. Begin preliminary capability assessment.",
        "agent_name": "Government Contracts Agent",
        "data_sources": ["Business Graph", "Government Data (Demo)"],
    },
]


# ╭──────────────────────────────────────────────────────────────────────╮
# │                   DEMO AGENT ACTIVITIES                             │
# ╰──────────────────────────────────────────────────────────────────────╯

SEED_ACTIVITIES = [
    {"agent_name": "Executive Agent", "action": "Completed daily business review",
     "detail": "Analyzed 15 KPIs, 23 customers, 18 leads, and 3 government opportunities.",
     "result": "Generated executive briefing with 6 priority items.",
     "data_sources": ["Business Memory", "Business Graph", "KPI Data"]},
    {"agent_name": "Sales Agent", "action": "Researched lead: David Okafor (OkaFor Logistics)",
     "detail": "Analyzed company profile, industry fit, and estimated deal value.",
     "result": "Lead score: 9/10. High-fit prospect. Recommended personalized outreach.",
     "data_sources": ["Business Graph", "Business Memory"]},
    {"agent_name": "Sales Agent", "action": "Updated lead scores for pipeline",
     "detail": "Re-scored 18 open leads based on engagement, fit, and timing.",
     "result": "3 leads upgraded, 2 leads downgraded. Pipeline value recalculated.",
     "data_sources": ["Business Graph"]},
    {"agent_name": "Finance Agent", "action": "Identified overdue invoices",
     "detail": "Scanned invoice records. Found 2 overdue: Acme Corp ($2,500, 12 days) and Pinnacle ($1,800, 7 days).",
     "result": "Created inbox items for follow-up. Total overdue: $4,300.",
     "data_sources": ["Financial Data (Demo)"]},
    {"agent_name": "Finance Agent", "action": "Analyzed recurring expenses for savings",
     "detail": "Reviewed 2 vendor contracts against usage patterns.",
     "result": "Identified $1,240/month in potential savings from CloudScale and SecureAuth.",
     "data_sources": ["Business Graph", "Financial Data (Demo)"]},
    {"agent_name": "Government Contracts Agent", "action": "Analyzed government opportunity GSA-IT-2026-1203",
     "detail": "Reviewed solicitation requirements against AgentMason capabilities.",
     "result": "Strong match. Recommended proceeding to bid/no-bid analysis. Deadline: Sep 1.",
     "data_sources": ["Business Graph", "Government Data (Demo)"]},
    {"agent_name": "Government Contracts Agent", "action": "Created compliance checklist for DOD-AI-2026-0847",
     "detail": "Extracted 12 compliance requirements from solicitation. Mapped against current certifications.",
     "result": "8/12 requirements met. 4 gaps identified (FedRAMP, ITAR, specific clearances).",
     "data_sources": ["Business Graph", "Government Data (Demo)"]},
    {"agent_name": "Customer Success Agent", "action": "Identified at-risk customer: Greenfield Analytics",
     "detail": "Detected 40% usage decline over 2 weeks. No recent support activity.",
     "result": "Flagged as medium churn risk. Recommended check-in call.",
     "data_sources": ["Product Data (Demo)", "Business Graph"]},
    {"agent_name": "Marketing Agent", "action": "Generated 3 LinkedIn post drafts",
     "detail": "Created content about: AI business automation, customer success story concept, government AI adoption.",
     "result": "Drafts saved for review. Marked as AI-generated content requiring approval.",
     "data_sources": ["Business Memory"]},
    {"agent_name": "Operations Agent", "action": "Identified process automation opportunity",
     "detail": "Invoice follow-up workflow currently manual. Average time: 45 minutes per follow-up cycle.",
     "result": "Recommended automated invoice reminder workflow. Estimated savings: 6 hours/month.",
     "data_sources": ["Business Memory", "Business Graph"]},
]


# ╭──────────────────────────────────────────────────────────────────────╮
# │                   DEMO BUSINESS METRICS                             │
# ╰──────────────────────────────────────────────────────────────────────╯

SEED_METRICS = [
    {"metric_name": "Tasks Automated", "metric_value": 47, "metric_unit": "count", "confidence": "actual", "description": "Total tasks completed by AgentMason agents"},
    {"metric_name": "Hours Potentially Saved", "metric_value": 32, "metric_unit": "hours", "confidence": "estimated", "description": "Estimated time saved through automation (based on avg task duration)"},
    {"metric_name": "Workflows Completed", "metric_value": 12, "metric_unit": "count", "confidence": "actual", "description": "Automated workflows successfully executed"},
    {"metric_name": "Human Approvals Processed", "metric_value": 8, "metric_unit": "count", "confidence": "actual", "description": "Actions reviewed and approved by humans"},
    {"metric_name": "Agent Actions", "metric_value": 156, "metric_unit": "count", "confidence": "actual", "description": "Total individual agent actions performed"},
    {"metric_name": "Issues Detected", "metric_value": 11, "metric_unit": "count", "confidence": "actual", "description": "Business issues proactively identified"},
    {"metric_name": "Opportunities Identified", "metric_value": 7, "metric_unit": "count", "confidence": "actual", "description": "Revenue or efficiency opportunities discovered"},
    {"metric_name": "Potential Savings", "metric_value": 1240, "metric_unit": "$/month", "confidence": "potential", "description": "Recurring cost reduction opportunities identified"},
    {"metric_name": "Leads Qualified", "metric_value": 14, "metric_unit": "count", "confidence": "actual", "description": "Leads researched and scored by Sales Agent"},
    {"metric_name": "Follow-ups Completed", "metric_value": 9, "metric_unit": "count", "confidence": "actual", "description": "Customer and lead follow-ups executed after approval"},
    {"metric_name": "Revenue Opportunities", "metric_value": 287000, "metric_unit": "$", "confidence": "estimated", "description": "Total value of identified revenue opportunities in pipeline"},
    {"metric_name": "Costs Potentially Reduced", "metric_value": 14880, "metric_unit": "$/year", "confidence": "potential", "description": "Annualized potential cost savings from identified optimizations"},
]


# ╭──────────────────────────────────────────────────────────────────────╮
# │                         SEED FUNCTION                               │
# ╰──────────────────────────────────────────────────────────────────────╯

def seed_business(db: Session, org_id: str, user_id: str, *, force: bool = False) -> dict:
    """Seed the full dogfood business workspace for an organization.

    Returns a summary dict with counts of created records.
    """
    from packages.orchestration.registry import SpecializedAgentRegistry

    summary: dict = {}

    # ── 1. Business Config ──────────────────────────────────────────────
    existing = db.query(BusinessConfig).filter_by(organization_id=org_id).first()
    if existing and not force:
        summary["config"] = "already_exists"
    else:
        if existing:
            db.delete(existing)
            db.flush()
        config = BusinessConfig(organization_id=org_id, **DEFAULT_BUSINESS)
        db.add(config)
        db.flush()
        summary["config"] = "created"

    # ── 2. Business Memories ────────────────────────────────────────────
    mem_svc = MemoryService(db)
    mem_count = 0
    for mem in SEED_MEMORIES:
        try:
            mem_svc.create(
                organization_id=org_id,
                category=mem["category"],
                title=mem["title"],
                content=mem["content"],
                source="agent_extraction",
                confidence=0.9,
                tags=["seed", "dogfood"],
                created_by=user_id,
            )
            mem_count += 1
        except Exception:
            logger.debug("Memory '%s' may already exist, skipping", mem["title"])
    summary["memories"] = mem_count

    # ── 3. Business Graph ───────────────────────────────────────────────
    graph_svc = GraphService(db)
    entity_map: dict[str, str] = {}  # name → id
    ent_count = 0
    for ent in SEED_ENTITIES:
        try:
            e = graph_svc.create_entity(
                organization_id=org_id,
                entity_type=ent["entity_type"],
                name=ent["name"],
                description=ent.get("description"),
                properties=ent.get("properties"),
                created_by=user_id,
            )
            entity_map[ent["name"]] = e.id
            ent_count += 1
        except Exception:
            # Try to find existing
            results, _ = graph_svc.search_entities(org_id, query=ent["name"], entity_type=ent["entity_type"])
            if results:
                entity_map[ent["name"]] = results[0].id
            logger.debug("Entity '%s' may already exist, skipping", ent["name"])
    summary["entities"] = ent_count

    rel_count = 0
    for src_name, tgt_name, rel_type, props in SEED_RELATIONSHIPS:
        src_id = entity_map.get(src_name)
        tgt_id = entity_map.get(tgt_name)
        if src_id and tgt_id:
            try:
                graph_svc.create_relationship(
                    organization_id=org_id,
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relationship_type=rel_type,
                    properties=props,
                    created_by=user_id,
                )
                rel_count += 1
            except Exception:
                logger.debug("Relationship %s->%s may already exist", src_name, tgt_name)
    summary["relationships"] = rel_count

    # ── 4. Specialized Agents ───────────────────────────────────────────
    registry = SpecializedAgentRegistry(db)
    agent_count = 0
    for agent_def in SEED_AGENTS:
        try:
            registry.register(
                organization_id=org_id,
                user_id=user_id,
                agent_type=agent_def["agent_type"],
                name=agent_def["name"],
                description=agent_def["description"],
                capabilities=agent_def["capabilities"],
                allowed_tools=agent_def["allowed_tools"],
                allowed_data_sources=agent_def["allowed_data_sources"],
                supported_tasks=agent_def["supported_tasks"],
                system_prompt=agent_def["system_prompt"],
                risk_level=agent_def["risk_level"],
                version="1.0.0",
            )
            agent_count += 1
        except Exception:
            logger.debug("Agent '%s' may already exist, skipping", agent_def["name"])
    summary["agents"] = agent_count

    # ── 5. Demo KPIs ────────────────────────────────────────────────────
    kpi_count = 0
    for kpi in SEED_KPIS:
        db.add(BusinessKPI(
            organization_id=org_id,
            name=kpi["name"],
            category=kpi["category"],
            value=kpi["value"],
            unit=kpi["unit"],
            target=kpi.get("target"),
            trend=kpi.get("trend"),
            is_demo_data=True,
            period="2026-08",
        ))
        kpi_count += 1
    summary["kpis"] = kpi_count

    # ── 6. Demo Inbox Items ─────────────────────────────────────────────
    inbox_count = 0
    for item in SEED_INBOX:
        db.add(BusinessInboxItem(
            organization_id=org_id,
            category=item["category"],
            priority=item.get("priority", "medium"),
            title=item["title"],
            description=item.get("description"),
            evidence=item.get("evidence"),
            recommended_action=item.get("recommended_action"),
            risk=item.get("risk"),
            why_it_matters=item.get("why_it_matters"),
            agent_name=item.get("agent_name"),
            data_sources=item.get("data_sources"),
            requires_approval=item.get("requires_approval", False),
            is_demo_data=True,
        ))
        inbox_count += 1
    summary["inbox_items"] = inbox_count

    # ── 7. Demo Agent Activities ────────────────────────────────────────
    act_count = 0
    base_time = datetime.now(timezone.utc) - timedelta(hours=8)
    for i, act in enumerate(SEED_ACTIVITIES):
        db.add(AgentActivity(
            organization_id=org_id,
            agent_name=act["agent_name"],
            action=act["action"],
            detail=act.get("detail"),
            result=act.get("result"),
            data_sources=act.get("data_sources"),
            is_demo_data=True,
            created_at=base_time + timedelta(minutes=i * 15),
        ))
        act_count += 1
    summary["activities"] = act_count

    # ── 8. Demo Business Metrics ────────────────────────────────────────
    met_count = 0
    for met in SEED_METRICS:
        db.add(BusinessMetric(
            organization_id=org_id,
            metric_name=met["metric_name"],
            metric_value=met["metric_value"],
            metric_unit=met["metric_unit"],
            confidence=met["confidence"],
            description=met.get("description"),
            is_demo_data=True,
        ))
        met_count += 1
    summary["metrics"] = met_count

    db.commit()
    logger.info("Dogfood seed complete for org %s: %s", org_id, summary)
    return summary
