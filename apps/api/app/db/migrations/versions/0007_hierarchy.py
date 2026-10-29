"""Migration #7: supervision hierarchy - model profiles, per-agent config,
review records, escalation flags, founder change requests on tasks, and
trace linkage on cost events.

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "model_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("tier", sa.String(10), nullable=False),
        sa.Column("price_in", sa.Float(), nullable=False, server_default="0"),
        sa.Column("price_out", sa.Float(), nullable=False, server_default="0"),
        *_timestamps(),
    )
    op.create_index("ix_model_profiles_user_id", "model_profiles", ["user_id"])

    # batch mode: SQLite cannot ALTER in a foreign key; Postgres just gets
    # plain ALTER TABLE statements.
    with op.batch_alter_table("agents") as batch:
        batch.add_column(sa.Column("model_profile_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("supervisor_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("instructions", sa.Text(), nullable=False,
                                   server_default=""))
        batch.add_column(sa.Column("max_revisions", sa.Integer(), nullable=False,
                                   server_default="2"))
        batch.add_column(sa.Column("requires_approval", sa.Boolean(), nullable=True))
        batch.create_foreign_key("fk_agents_model_profile_id", "model_profiles",
                                 ["model_profile_id"], ["id"])
        batch.create_foreign_key("fk_agents_supervisor_id", "agents",
                                 ["supervisor_id"], ["id"])

    op.add_column("projects", sa.Column(
        "instructions", sa.Text(), nullable=False, server_default=""))

    with op.batch_alter_table("cost_events") as batch:
        batch.add_column(sa.Column("task_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("call_role", sa.String(20), nullable=False,
                                   server_default="work"))
        batch.create_foreign_key("fk_cost_events_task_id", "tasks", ["task_id"], ["id"])
        batch.create_index("ix_cost_events_task_id", ["task_id"])

    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("founder_feedback", sa.Text(), nullable=False,
                                   server_default=""))
        batch.add_column(sa.Column("revises_artifact_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_tasks_revises_artifact_id", "artifacts",
                                 ["revises_artifact_id"], ["id"])

    op.create_table(
        "task_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("worker_agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("reviewer_agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("reviewed_output", sa.JSON(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_task_reviews_project_id", "task_reviews", ["project_id"])
    op.create_index("ix_task_reviews_task_id", "task_reviews", ["task_id"])

    op.create_table(
        "flags",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), sa.ForeignKey("artifacts.id"), nullable=True),
        sa.Column("raised_by_agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("holder_agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("chain", sa.JSON(), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=False),
        sa.Column("approval_request_id", sa.Uuid(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_flags_project_id", "flags", ["project_id"])
    op.create_index("ix_flags_task_id", "flags", ["task_id"])


def downgrade() -> None:
    op.drop_table("flags")
    op.drop_table("task_reviews")
    with op.batch_alter_table("tasks") as batch:
        batch.drop_constraint("fk_tasks_revises_artifact_id", type_="foreignkey")
        batch.drop_column("revises_artifact_id")
        batch.drop_column("founder_feedback")
    with op.batch_alter_table("cost_events") as batch:
        batch.drop_index("ix_cost_events_task_id")
        batch.drop_constraint("fk_cost_events_task_id", type_="foreignkey")
        batch.drop_column("call_role")
        batch.drop_column("task_id")
    op.drop_column("projects", "instructions")
    with op.batch_alter_table("agents") as batch:
        batch.drop_constraint("fk_agents_supervisor_id", type_="foreignkey")
        batch.drop_constraint("fk_agents_model_profile_id", type_="foreignkey")
        for col in ("requires_approval", "max_revisions", "instructions",
                    "supervisor_id", "model_profile_id"):
            batch.drop_column(col)
    op.drop_table("model_profiles")
