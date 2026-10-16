"""Add durable digest preferences, jobs, and in-app delivery records."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261016_0006"
down_revision: str | None = "20261016_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    job_status = postgresql.ENUM(
        "CLAIMED", "DELIVERED", "FAILED", name="digestjobstatus", create_type=False
    )
    notification_status = postgresql.ENUM(
        "DELIVERED", "FAILED", name="notificationstatus", create_type=False
    )
    job_status.create(op.get_bind(), checkfirst=True)
    notification_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "digest_preferences",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("local_time", sa.String(5), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_dispatched_at", sa.DateTime(timezone=True), nullable=True),
        *_identity_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id"),
    )
    op.create_index(
        "ix_digest_preferences_due", "digest_preferences", ["enabled", "next_due_at"]
    )

    op.create_table(
        "digest_jobs",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("preference_id", sa.Uuid(), nullable=False),
        sa.Column("job_key", sa.String(180), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("forecast_id", sa.Uuid(), nullable=True),
        sa.Column("insight_kind", sa.String(60), nullable=False),
        sa.Column("insight_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("subject", sa.String(180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("error", sa.String(500), nullable=True),
        *_identity_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["preference_id"], ["digest_preferences.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["calculation_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["forecast_id"], ["forecasts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_key"),
    )
    op.create_index("ix_digest_jobs_tenant_created", "digest_jobs", ["tenant_id", "created_at"])

    op.create_table(
        "in_app_notifications",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("digest_job_id", sa.Uuid(), nullable=False),
        sa.Column("dedupe_key", sa.String(180), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("status", notification_status, nullable=False),
        sa.Column("subject", sa.String(180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        *_identity_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["digest_job_id"], ["digest_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "dedupe_key"),
    )
    op.create_index(
        "ix_notifications_user_created",
        "in_app_notifications",
        ["tenant_id", "user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("in_app_notifications")
    op.drop_table("digest_jobs")
    op.drop_table("digest_preferences")
    postgresql.ENUM(name="notificationstatus").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="digestjobstatus").drop(op.get_bind(), checkfirst=True)
