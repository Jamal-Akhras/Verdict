"""Migration #2: feasibility_reports, cost_events, model_calls

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feasibility_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("mvp_scope", sa.JSON(), nullable=False),
        sa.Column("do_not_build", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("validation_plan", sa.JSON(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("cost_estimate", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feasibility_reports_project_id", "feasibility_reports", ["project_id"])

    op.create_table(
        "cost_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("agent_slug", sa.String(100), nullable=True),
        sa.Column("task_type", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cost_events_project_id", "cost_events", ["project_id"])
    op.create_index("ix_cost_events_agent_slug", "cost_events", ["agent_slug"])

    op.create_table(
        "model_calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cost_event_id", sa.Uuid(), sa.ForeignKey("cost_events.id"), nullable=False, unique=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("output_schema_name", sa.String(100), nullable=True),
        sa.Column("parse_ok", sa.Boolean(), nullable=False),
        sa.Column("router_decision", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("model_calls")
    op.drop_table("cost_events")
    op.drop_table("feasibility_reports")
