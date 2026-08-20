"""Built-in workflow templates for common business processes."""

from __future__ import annotations

from typing import Any


class WorkflowTemplateRegistry:
    """Registry for reusable workflow templates."""

    def __init__(self) -> None:
        self._templates: dict[str, dict[str, Any]] = {}
        self._register_defaults()

    def register(self, template: dict[str, Any]) -> None:
        self._templates[template["name"]] = template

    def get(self, name: str) -> dict[str, Any] | None:
        return self._templates.get(name)

    def list(self) -> list[dict[str, Any]]:
        return list(self._templates.values())

    def list_by_category(self, category: str) -> list[dict[str, Any]]:
        return [t for t in self._templates.values() if t.get("template_category") == category]

    def _register_defaults(self) -> None:
        for tmpl in _DEFAULT_TEMPLATES:
            self.register(tmpl)


_DEFAULT_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "Customer Onboarding",
        "description": "Onboard a new customer: validate information, create CRM records, send welcome communication, and schedule follow-up.",
        "trigger": "new_customer",
        "template_category": "customer",
        "is_template": True,
        "inputs": {
            "customer_name": {"type": "string", "required": True, "description": "Name of the customer or company"},
            "customer_email": {"type": "string", "required": False, "description": "Customer email address"},
        },
        "steps": [
            {
                "index": 0,
                "name": "validate_customer",
                "description": "Look up and validate customer information in business systems",
                "type": "action",
                "tool": "search_business_memory",
                "tool_input": {"query": "{customer_name}"},
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 1,
                "name": "check_existing_records",
                "description": "Search business graph for existing customer records",
                "type": "action",
                "tool": "search_business_graph",
                "tool_input": {"query": "{customer_name}", "entity_type": "customer"},
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 2,
                "name": "retrieve_onboarding_policy",
                "description": "Retrieve the onboarding policy and required steps from knowledge base",
                "type": "action",
                "tool": "search_business_knowledge",
                "tool_input": {"query": "customer onboarding policy procedure"},
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 3,
                "name": "create_crm_record",
                "description": "Create or update the customer record in the business graph",
                "type": "action",
                "tool": "search_business_graph",
                "tool_input": {"query": "{customer_name}"},
                "risk_level": "medium",
                "requires_approval": False,
            },
            {
                "index": 4,
                "name": "draft_welcome_email",
                "description": "Draft a welcome email to the new customer",
                "type": "action",
                "tool": "create_email_draft",
                "tool_input": {"to": "{customer_email}", "subject": "Welcome to our service"},
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 5,
                "name": "approve_welcome_email",
                "description": "Get approval before sending the welcome email",
                "type": "approval",
                "tool": None,
                "risk_level": "medium",
                "requires_approval": True,
            },
            {
                "index": 6,
                "name": "send_welcome_email",
                "description": "Send the approved welcome email",
                "type": "action",
                "tool": "send_email",
                "tool_input": {},
                "risk_level": "medium",
                "requires_approval": False,
                "depends_on": [5],
            },
            {
                "index": 7,
                "name": "schedule_followup",
                "description": "Schedule a follow-up meeting or call",
                "type": "action",
                "tool": "create_calendar_event",
                "tool_input": {"summary": "Customer Onboarding Follow-up: {customer_name}"},
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 8,
                "name": "record_completion",
                "description": "Record the onboarding completion in business memory",
                "type": "action",
                "tool": "create_business_memory",
                "tool_input": {
                    "category": "process",
                    "title": "Customer Onboarding: {customer_name}",
                    "content": "Customer onboarding completed successfully",
                },
                "risk_level": "low",
                "requires_approval": False,
            },
        ],
        "approval_policy": {
            "require_approval_for": ["send_email", "send_welcome_email"],
        },
        "retry_policy": {"max_retries": 2, "backoff_seconds": 30},
        "cost_policy": {"max_token_usage": 50000, "max_llm_calls": 20, "max_tool_calls": 30},
    },
    {
        "name": "Invoice Follow-Up",
        "description": "Find overdue invoices, check payment policies, draft and send follow-up communications.",
        "trigger": "overdue_invoices",
        "template_category": "finance",
        "is_template": True,
        "inputs": {
            "threshold_amount": {"type": "number", "required": False, "description": "Minimum invoice amount to follow up on", "default": 0},
            "days_overdue": {"type": "number", "required": False, "description": "Minimum days overdue", "default": 7},
        },
        "steps": [
            {
                "index": 0,
                "name": "find_overdue_invoices",
                "description": "Search for overdue invoices in business systems",
                "type": "action",
                "tool": "search_business_memory",
                "tool_input": {"query": "overdue invoice"},
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 1,
                "name": "retrieve_payment_policy",
                "description": "Retrieve the company payment and collections policy",
                "type": "action",
                "tool": "search_business_knowledge",
                "tool_input": {"query": "payment policy collections overdue invoice"},
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 2,
                "name": "process_each_invoice",
                "description": "Process each overdue invoice — look up customer, draft reminder, request approval, send",
                "type": "loop",
                "tool": None,
                "risk_level": "medium",
                "requires_approval": False,
                "loop_config": {
                    "over": "step_output.find_overdue_invoices.results",
                    "max_iterations": 50,
                    "steps": [
                        {
                            "name": "lookup_customer",
                            "description": "Look up customer information for this invoice",
                            "type": "action",
                            "tool": "search_business_graph",
                            "tool_input": {"query": "{item.customer_name}", "entity_type": "customer"},
                            "risk_level": "low",
                        },
                        {
                            "name": "check_amount_threshold",
                            "description": "Check if invoice requires manager approval",
                            "type": "condition",
                            "condition": {
                                "field": "item.amount",
                                "operator": "gt",
                                "value": 10000,
                                "source": "context",
                            },
                        },
                        {
                            "name": "draft_reminder",
                            "description": "Draft a payment reminder email",
                            "type": "action",
                            "tool": "create_email_draft",
                            "tool_input": {"subject": "Payment Reminder: Invoice {item.invoice_id}"},
                            "risk_level": "low",
                        },
                        {
                            "name": "approve_reminder",
                            "description": "Get approval to send the payment reminder",
                            "type": "approval",
                            "risk_level": "medium",
                            "requires_approval": True,
                        },
                        {
                            "name": "send_reminder",
                            "description": "Send the approved payment reminder",
                            "type": "action",
                            "tool": "send_email",
                            "risk_level": "medium",
                        },
                        {
                            "name": "record_action",
                            "description": "Record the follow-up action in business memory",
                            "type": "action",
                            "tool": "create_business_memory",
                            "tool_input": {
                                "category": "process",
                                "title": "Invoice Follow-Up: {item.invoice_id}",
                                "content": "Payment reminder sent for invoice {item.invoice_id}",
                            },
                            "risk_level": "low",
                        },
                    ],
                },
            },
            {
                "index": 3,
                "name": "generate_summary",
                "description": "Generate a summary report of all follow-up actions taken",
                "type": "action",
                "tool": "search_business_memory",
                "tool_input": {"query": "invoice follow-up"},
                "risk_level": "low",
                "requires_approval": False,
            },
        ],
        "approval_policy": {
            "require_approval_for": ["send_email", "send_reminder"],
            "auto_approve_below": 1000,
        },
        "retry_policy": {"max_retries": 2, "backoff_seconds": 60},
        "cost_policy": {"max_token_usage": 100000, "max_llm_calls": 50, "max_tool_calls": 200},
    },
    {
        "name": "Lead Qualification",
        "description": "Qualify a new sales lead: research, enrich, score, update CRM, and notify sales team.",
        "trigger": "new_lead",
        "template_category": "sales",
        "is_template": True,
        "inputs": {
            "lead_name": {"type": "string", "required": True, "description": "Name of the lead or company"},
            "lead_email": {"type": "string", "required": False, "description": "Lead contact email"},
        },
        "steps": [
            {
                "index": 0,
                "name": "research_company",
                "description": "Search for information about the lead company",
                "type": "action",
                "tool": "search_business_knowledge",
                "tool_input": {"query": "{lead_name}"},
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 1,
                "name": "check_existing_relationship",
                "description": "Check if we have an existing relationship with this lead",
                "type": "action",
                "tool": "search_business_graph",
                "tool_input": {"query": "{lead_name}"},
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 2,
                "name": "enrich_information",
                "description": "Search business files and emails for additional context",
                "type": "action",
                "tool": "search_business_files",
                "tool_input": {"query": "{lead_name}"},
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 3,
                "name": "score_lead",
                "description": "Record lead qualification score based on gathered information",
                "type": "action",
                "tool": "create_business_memory",
                "tool_input": {
                    "category": "business_fact",
                    "title": "Lead Score: {lead_name}",
                    "content": "Lead qualification analysis for {lead_name}",
                },
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 4,
                "name": "notify_sales",
                "description": "Draft notification email to sales team about qualified lead",
                "type": "action",
                "tool": "create_email_draft",
                "tool_input": {"subject": "New Qualified Lead: {lead_name}"},
                "risk_level": "low",
                "requires_approval": False,
            },
        ],
        "retry_policy": {"max_retries": 2, "backoff_seconds": 30},
        "cost_policy": {"max_token_usage": 30000, "max_llm_calls": 15, "max_tool_calls": 20},
    },
    {
        "name": "Employee Onboarding",
        "description": "Onboard a new employee: create tasks, prepare documents, notify departments, schedule meetings.",
        "trigger": "new_employee",
        "template_category": "hr",
        "is_template": True,
        "inputs": {
            "employee_name": {"type": "string", "required": True, "description": "Name of the new employee"},
            "department": {"type": "string", "required": True, "description": "Department the employee is joining"},
            "start_date": {"type": "string", "required": True, "description": "Employee start date"},
        },
        "steps": [
            {
                "index": 0,
                "name": "retrieve_onboarding_checklist",
                "description": "Retrieve the employee onboarding checklist from knowledge base",
                "type": "action",
                "tool": "search_business_knowledge",
                "tool_input": {"query": "employee onboarding checklist {department}"},
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 1,
                "name": "create_onboarding_tasks",
                "description": "Create onboarding task records",
                "type": "action",
                "tool": "create_business_memory",
                "tool_input": {
                    "category": "process",
                    "title": "Onboarding Tasks: {employee_name}",
                    "content": "Onboarding tasks created for {employee_name} joining {department}",
                },
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 2,
                "name": "notify_department",
                "description": "Draft notification to the department about the new hire",
                "type": "action",
                "tool": "create_email_draft",
                "tool_input": {"subject": "New Team Member: {employee_name} joining {department}"},
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 3,
                "name": "approve_notification",
                "description": "Approve department notification before sending",
                "type": "approval",
                "risk_level": "medium",
                "requires_approval": True,
            },
            {
                "index": 4,
                "name": "send_notification",
                "description": "Send the approved department notification",
                "type": "action",
                "tool": "send_email",
                "risk_level": "medium",
                "requires_approval": False,
                "depends_on": [3],
            },
            {
                "index": 5,
                "name": "schedule_orientation",
                "description": "Schedule orientation meeting for the new employee",
                "type": "action",
                "tool": "create_calendar_event",
                "tool_input": {"summary": "Orientation: {employee_name}", "start_date": "{start_date}"},
                "risk_level": "low",
                "requires_approval": False,
            },
            {
                "index": 6,
                "name": "record_completion",
                "description": "Record onboarding initiation in business memory",
                "type": "action",
                "tool": "create_business_memory",
                "tool_input": {
                    "category": "process",
                    "title": "Employee Onboarding Started: {employee_name}",
                    "content": "{employee_name} onboarding initiated for {department}, start date: {start_date}",
                },
                "risk_level": "low",
                "requires_approval": False,
            },
        ],
        "approval_policy": {
            "require_approval_for": ["send_email"],
        },
        "retry_policy": {"max_retries": 2, "backoff_seconds": 30},
        "cost_policy": {"max_token_usage": 30000, "max_llm_calls": 15, "max_tool_calls": 25},
    },
]
