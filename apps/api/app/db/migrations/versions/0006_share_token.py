"""Migration #6: public share tokens on feasibility reports

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "feasibility_reports",
        sa.Column("share_token", sa.String(64), nullable=True),
    )
    # unique INDEX (not constraint): works on both Postgres and SQLite
    op.create_index(
        "ix_feasibility_reports_share_token",
        "feasibility_reports",
        ["share_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_feasibility_reports_share_token", table_name="feasibility_reports")
    op.drop_column("feasibility_reports", "share_token")
