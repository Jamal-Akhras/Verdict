"""Migration #3: agent_templates, agents

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("initials", sa.String(4), nullable=False),
        sa.Column("team", sa.String(50), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("default_tools", sa.JSON(), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("output_types", sa.JSON(), nullable=False),
        sa.Column("task_types", sa.JSON(), nullable=False),
        sa.Column("default_budget_usd", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(10), nullable=False),
        sa.Column("authority_default", sa.String(10), nullable=False),
        sa.Column("approval_requirement", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", "version", name="uq_template_slug_version"),
    )
    op.create_index("ix_agent_templates_slug", "agent_templates", ["slug"])

    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("template_id", sa.Uuid(), sa.ForeignKey("agent_templates.id"), nullable=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("initials", sa.String(4), nullable=False),
        sa.Column("team", sa.String(50), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("authority", sa.String(10), nullable=False),
        sa.Column("risk_level", sa.String(10), nullable=False),
        sa.Column("budget_max_usd", sa.Float(), nullable=False),
        sa.Column("created_by", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agents_project_id", "agents", ["project_id"])
    op.create_index("ix_agents_slug", "agents", ["slug"])


def downgrade() -> None:
    op.drop_table("agents")
    op.drop_table("agent_templates")
