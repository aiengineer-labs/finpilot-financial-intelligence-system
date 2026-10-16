"""Add durable agent executions, events, recommendations, and verification."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261016_0004"
down_revision: str | None = "20261016_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    run_status = postgresql.ENUM(
        "RUNNING", "COMPLETED", "REJECTED", "FAILED",
        name="agentrunstatus", create_type=False,
    )
    verification_status = postgresql.ENUM(
        "ACCEPT", "REVISE", "REJECT", "INSUFFICIENT_DATA",
        name="verificationstatus", create_type=False,
    )
    run_status.create(op.get_bind(), checkfirst=True)
    verification_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "agent_executions",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("forecast_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_run_id", sa.Uuid(), nullable=True),
        sa.Column("question", sa.String(1000), nullable=False),
        sa.Column("intent", sa.String(40), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("verification_status", verification_status, nullable=False),
        sa.Column("final_response", sa.Text(), nullable=False),
        sa.Column("graph_version", sa.String(40), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("model_id", sa.String(120), nullable=False),
        sa.Column("revision_attempts", sa.Integer(), nullable=False),
        sa.Column("total_latency_ms", sa.Integer(), nullable=False),
        sa.Column("total_input_tokens", sa.Integer(), nullable=False),
        sa.Column("total_output_tokens", sa.Integer(), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE",
            name="fk_agent_executions_tenant_id_tenants",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], ondelete="RESTRICT",
            name="fk_agent_executions_requested_by_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["calculation_snapshots.id"], ondelete="RESTRICT",
            name="fk_agent_executions_snapshot_id_calculation_snapshots",
        ),
        sa.ForeignKeyConstraint(
            ["forecast_id"], ["forecasts.id"], ondelete="RESTRICT",
            name="fk_agent_executions_forecast_id_forecasts",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_run_id"], ["scenario_runs.id"], ondelete="RESTRICT",
            name="fk_agent_executions_scenario_run_id_scenario_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_executions"),
    )
    op.create_index(
        "ix_agent_executions_tenant_created", "agent_executions", ["tenant_id", "created_at"]
    )
    op.create_table(
        "agent_events",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("node", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("model_id", sa.String(120), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        *_identity_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE",
            name="fk_agent_events_tenant_id_tenants",
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["agent_executions.id"], ondelete="CASCADE",
            name="fk_agent_events_execution_id_agent_executions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_events"),
        sa.UniqueConstraint("execution_id", "sequence", name="uq_agent_events_execution_id"),
    )
    op.create_index(
        "ix_agent_events_execution_sequence", "agent_events", ["execution_id", "sequence"]
    )
    op.create_table(
        "recommendations",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("confidence_bps", sa.Integer(), nullable=False),
        sa.Column("verification_status", verification_status, nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE",
            name="fk_recommendations_tenant_id_tenants",
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["agent_executions.id"], ondelete="CASCADE",
            name="fk_recommendations_execution_id_agent_executions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recommendations"),
    )
    op.create_index(
        "ix_recommendations_tenant_execution", "recommendations",
        ["tenant_id", "execution_id"],
    )
    op.create_table(
        "financial_verifications",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_id", sa.Uuid(), nullable=True),
        sa.Column("status", verification_status, nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("checked_values", sa.JSON(), nullable=False),
        sa.Column("verifier_version", sa.String(40), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE",
            name="fk_financial_verifications_tenant_id_tenants",
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["agent_executions.id"], ondelete="CASCADE",
            name="fk_financial_verifications_execution_id_agent_executions",
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["recommendations.id"], ondelete="CASCADE",
            name="fk_financial_verifications_recommendation_id_recommendations",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_financial_verifications"),
    )
    op.create_index(
        "ix_verifications_tenant_execution", "financial_verifications",
        ["tenant_id", "execution_id"],
    )


def downgrade() -> None:
    op.drop_table("financial_verifications")
    op.drop_table("recommendations")
    op.drop_table("agent_events")
    op.drop_table("agent_executions")
    postgresql.ENUM(name="verificationstatus").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="agentrunstatus").drop(op.get_bind(), checkfirst=True)
