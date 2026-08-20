"""Add workflow engine models.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Workflows table
    op.create_table(
        "workflows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("trigger", sa.String(255), nullable=True),
        sa.Column("status", sa.Enum("draft", "active", "inactive", "archived", name="workflowstatus"), nullable=False, server_default="draft"),
        sa.Column("steps", sa.JSON, nullable=True),
        sa.Column("inputs", sa.JSON, nullable=True),
        sa.Column("conditions", sa.JSON, nullable=True),
        sa.Column("tools", sa.JSON, nullable=True),
        sa.Column("required_permissions", sa.JSON, nullable=True),
        sa.Column("approval_policy", sa.JSON, nullable=True),
        sa.Column("retry_policy", sa.JSON, nullable=True),
        sa.Column("risk_policy", sa.JSON, nullable=True),
        sa.Column("cost_policy", sa.JSON, nullable=True),
        sa.Column("max_steps", sa.Integer, nullable=False, server_default="50"),
        sa.Column("max_iterations", sa.Integer, nullable=False, server_default="100"),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="3600"),
        sa.Column("is_template", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("template_category", sa.String(100), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Workflow executions table
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id"), nullable=False, index=True),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("status", sa.Enum(
            "draft", "planned", "waiting_for_approval", "running", "paused",
            "waiting_for_input", "completed", "failed", "cancelled",
            name="executionstatus"
        ), nullable=False, server_default="planned"),
        sa.Column("plan", sa.JSON, nullable=True),
        sa.Column("inputs", sa.JSON, nullable=True),
        sa.Column("outputs", sa.JSON, nullable=True),
        sa.Column("context", sa.JSON, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("current_step_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_steps", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed_steps", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_token_usage", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tool_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_llm_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("objective", sa.Text, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Workflow step executions table
    op.create_table(
        "workflow_step_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("execution_id", sa.String(36), sa.ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("step_name", sa.String(255), nullable=False),
        sa.Column("step_type", sa.String(50), nullable=False, server_default="action"),
        sa.Column("status", sa.Enum(
            "pending", "running", "completed", "failed", "skipped",
            "waiting_for_approval", "waiting_for_input", "cancelled",
            name="stepstatus"
        ), nullable=False, server_default="pending"),
        sa.Column("tool_name", sa.String(255), nullable=True),
        sa.Column("tool_input", sa.JSON, nullable=True),
        sa.Column("tool_output", sa.JSON, nullable=True),
        sa.Column("risk_level", sa.Enum("low", "medium", "high", "critical", name="risklevel"), nullable=True),
        sa.Column("requires_approval", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("approval_id", sa.String(36), nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="3"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Approval requests table
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("execution_id", sa.String(36), sa.ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("step_execution_id", sa.String(36), nullable=True, index=True),
        sa.Column("status", sa.Enum("pending", "approved", "rejected", "expired", "cancelled", name="approvalstatus"), nullable=False, server_default="pending"),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("action_description", sa.Text, nullable=False),
        sa.Column("action_parameters", sa.JSON, nullable=True),
        sa.Column("risk_level", sa.Enum("low", "medium", "high", "critical", name="risklevel_approval"), nullable=False, server_default="medium"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("data_summary", sa.JSON, nullable=True),
        sa.Column("target_system", sa.String(255), nullable=True),
        sa.Column("expected_outcome", sa.Text, nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
        sa.Column("modified_parameters", sa.JSON, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Workflow audit log table
    op.create_table(
        "workflow_audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("workflow_id", sa.String(36), nullable=True, index=True),
        sa.Column("execution_id", sa.String(36), nullable=True, index=True),
        sa.Column("step_execution_id", sa.String(36), nullable=True),
        sa.Column("action", sa.Enum(
            "workflow_created", "workflow_updated", "workflow_deleted",
            "execution_started", "execution_completed", "execution_failed",
            "execution_cancelled", "execution_paused", "execution_resumed",
            "step_started", "step_completed", "step_failed", "step_skipped", "step_retried",
            "approval_requested", "approval_granted", "approval_rejected", "approval_expired",
            "tool_executed", "tool_failed",
            "cost_limit_reached", "human_intervention",
            name="auditaction"
        ), nullable=False, index=True),
        sa.Column("agent_name", sa.String(255), nullable=True),
        sa.Column("tool_name", sa.String(255), nullable=True),
        sa.Column("risk_level", sa.Enum("low", "medium", "high", "critical", name="risklevel_audit"), nullable=True),
        sa.Column("approval_status", sa.Enum("pending", "approved", "rejected", "expired", "cancelled", name="approvalstatus_audit"), nullable=True),
        sa.Column("input_summary", sa.JSON, nullable=True),
        sa.Column("output_summary", sa.JSON, nullable=True),
        sa.Column("error_info", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("workflow_audit_log")
    op.drop_table("approval_requests")
    op.drop_table("workflow_step_executions")
    op.drop_table("workflow_executions")
    op.drop_table("workflows")
