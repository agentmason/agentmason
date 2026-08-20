"""Add dogfood business tables.

Revision ID: 0007
Revises: 0006_add_multi_agent_orchestration
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_add_dogfood_business"
down_revision = "0006_add_multi_agent_orchestration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── BusinessConfig ──────────────────────────────────────────────
    op.create_table(
        "business_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False, unique=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=True),
        sa.Column("business_type", sa.String(255), nullable=True),
        sa.Column("tagline", sa.String(500), nullable=True),
        sa.Column("departments", sa.JSON, nullable=True),
        sa.Column("business_activities", sa.JSON, nullable=True),
        sa.Column("goals", sa.JSON, nullable=True),
        sa.Column("kpis", sa.JSON, nullable=True),
        sa.Column("demo_mode", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_business_configs_org", "business_configs", ["organization_id"])

    # ── BusinessKPI ─────────────────────────────────────────────────
    op.create_table(
        "business_kpis",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("target", sa.Float, nullable=True),
        sa.Column("trend", sa.String(20), nullable=True),
        sa.Column("is_demo_data", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("period", sa.String(30), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_business_kpis_org", "business_kpis", ["organization_id"])

    # ── BusinessInboxItem ───────────────────────────────────────────
    op.create_table(
        "business_inbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("evidence", sa.Text, nullable=True),
        sa.Column("recommended_action", sa.Text, nullable=True),
        sa.Column("risk", sa.String(255), nullable=True),
        sa.Column("why_it_matters", sa.Text, nullable=True),
        sa.Column("agent_name", sa.String(100), nullable=True),
        sa.Column("workflow_id", sa.String(36), nullable=True),
        sa.Column("data_sources", sa.JSON, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("requires_approval", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("is_demo_data", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_business_inbox_org", "business_inbox", ["organization_id"])

    # ── AgentActivity ───────────────────────────────────────────────
    op.create_table(
        "agent_activities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("action", sa.String(500), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column("workflow_id", sa.String(36), nullable=True),
        sa.Column("data_sources", sa.JSON, nullable=True),
        sa.Column("is_demo_data", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_activities_org", "agent_activities", ["organization_id"])

    # ── BusinessMetric ──────────────────────────────────────────────
    op.create_table(
        "business_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("metric_name", sa.String(255), nullable=False),
        sa.Column("metric_value", sa.Float, nullable=False),
        sa.Column("metric_unit", sa.String(50), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False, server_default="estimated"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_demo_data", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_business_metrics_org", "business_metrics", ["organization_id"])


def downgrade() -> None:
    op.drop_table("business_metrics")
    op.drop_table("agent_activities")
    op.drop_table("business_inbox")
    op.drop_table("business_kpis")
    op.drop_table("business_configs")
