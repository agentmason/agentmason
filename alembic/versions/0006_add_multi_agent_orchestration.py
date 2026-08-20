"""Add multi-agent orchestration models.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Specialized agents table
    op.create_table(
        "specialized_agents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("agent_type", sa.String(100), nullable=False, index=True),
        sa.Column("capabilities", sa.JSON, nullable=True),
        sa.Column("allowed_tools", sa.JSON, nullable=True),
        sa.Column("allowed_data_sources", sa.JSON, nullable=True),
        sa.Column("permissions", sa.JSON, nullable=True),
        sa.Column("supported_tasks", sa.JSON, nullable=True),
        sa.Column("model_config", sa.JSON, nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column(
            "risk_level",
            sa.Enum("low", "medium", "high", "critical", name="agentrisklevel"),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", "deprecated", name="agentstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("version", sa.String(50), nullable=False, server_default="1.0.0"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Orchestration executions table
    op.create_table(
        "orchestration_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("objective", sa.Text, nullable=False),
        sa.Column("plan", sa.JSON, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "planning", "executing", "waiting_for_approval",
                "merging_results", "resolving_conflicts",
                "completed", "failed", "cancelled",
                name="orchestrationstatus",
            ),
            nullable=False,
            server_default="planning",
        ),
        sa.Column("final_summary", sa.Text, nullable=True),
        sa.Column("final_recommendation", sa.JSON, nullable=True),
        sa.Column("final_confidence", sa.Float, nullable=True),
        sa.Column("conflicts", sa.JSON, nullable=True),
        sa.Column("conflict_resolution", sa.JSON, nullable=True),
        sa.Column("workflow_execution_id", sa.String(36), nullable=True),
        sa.Column("total_token_usage", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tool_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_llm_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_agent_tasks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Agent tasks table
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "orchestration_id", sa.String(36),
            sa.ForeignKey("orchestration_executions.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "agent_id", sa.String(36),
            sa.ForeignKey("specialized_agents.id"),
            nullable=False, index=True,
        ),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("objective", sa.Text, nullable=False),
        sa.Column("context", sa.JSON, nullable=True),
        sa.Column("expected_output_type", sa.String(100), nullable=True),
        sa.Column("capabilities_required", sa.JSON, nullable=True),
        sa.Column("execution_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("depends_on", sa.JSON, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "running", "completed", "failed", "cancelled", "timed_out",
                name="agenttaskstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("findings", sa.JSON, nullable=True),
        sa.Column("recommendations", sa.JSON, nullable=True),
        sa.Column("evidence", sa.JSON, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("risks", sa.JSON, nullable=True),
        sa.Column("required_actions", sa.JSON, nullable=True),
        sa.Column("sources", sa.JSON, nullable=True),
        sa.Column("token_usage", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tool_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("llm_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Agent communications table
    op.create_table(
        "agent_communications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "orchestration_id", sa.String(36),
            sa.ForeignKey("orchestration_executions.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("from_agent_id", sa.String(36), nullable=False),
        sa.Column("to_agent_id", sa.String(36), nullable=True),
        sa.Column("message_type", sa.String(100), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("structured_data", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("agent_communications")
    op.drop_table("agent_tasks")
    op.drop_table("orchestration_executions")
    op.drop_table("specialized_agents")
