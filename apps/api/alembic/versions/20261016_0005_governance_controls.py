"""Add versioned governance, risk, evaluation, and human-review controls."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261016_0005"
down_revision: str | None = "20261016_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    artifact_status = postgresql.ENUM(
        "DRAFT",
        "APPROVED",
        "REJECTED",
        "SUPERSEDED",
        name="governanceartifactstatus",
        create_type=False,
    )
    risk_level = postgresql.ENUM(
        "LOW", "MEDIUM", "HIGH", "CRITICAL", name="risklevel", create_type=False
    )
    review_status = postgresql.ENUM(
        "PENDING", "RESOLVED", name="humanreviewstatus", create_type=False
    )
    decision_outcome = postgresql.ENUM(
        "APPROVE",
        "REJECT",
        "REQUEST_INFORMATION",
        "REQUEST_REVISION",
        name="humandecisionoutcome",
        create_type=False,
    )
    gate_status = postgresql.ENUM(
        "PASS", "FAIL", "NOT_RUN", name="evaluationgatestatus", create_type=False
    )
    for enum in (artifact_status, risk_level, review_status, decision_outcome, gate_status):
        enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "agent_executions",
        sa.Column("artifact_lineage", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "recommendations",
        sa.Column("artifact_lineage", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    op.create_table(
        "governance_artifacts",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("status", artifact_status, nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("approval_source", sa.String(80), nullable=False),
        sa.Column("approval_reason", sa.String(500), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollback_artifact_id", sa.Uuid(), nullable=True),
        *_identity_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["rollback_artifact_id"], ["governance_artifacts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "artifact_type", "name", "version"),
    )
    op.create_index(
        "ix_governance_artifacts_tenant_status", "governance_artifacts", ["tenant_id", "status"]
    )

    op.create_table(
        "risk_register_entries",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("risk_id", sa.String(40), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("likelihood", risk_level, nullable=False),
        sa.Column("impact", risk_level, nullable=False),
        sa.Column("affected_assets", sa.JSON(), nullable=False),
        sa.Column("cause", sa.Text(), nullable=False),
        sa.Column("mitigation", sa.Text(), nullable=False),
        sa.Column("test_evidence", sa.JSON(), nullable=False),
        sa.Column("owner_role", sa.String(80), nullable=False),
        sa.Column("residual_risk", risk_level, nullable=False),
        sa.Column("acceptance_status", sa.String(40), nullable=False),
        sa.Column("exception_record", sa.String(500), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("review_on", sa.Date(), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "risk_id", "version"),
    )
    op.create_index(
        "ix_risk_register_tenant_level", "risk_register_entries", ["tenant_id", "residual_risk"]
    )

    op.create_table(
        "evaluation_runs",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.String(120), nullable=False),
        sa.Column("dataset_version", sa.String(80), nullable=False),
        sa.Column("sampling_method", sa.String(160), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("status", gate_status, nullable=False),
        sa.Column("code_version", sa.String(80), nullable=False),
        sa.Column("model_id", sa.String(120), nullable=True),
        sa.Column("failures", sa.JSON(), nullable=False),
        sa.Column("reviewer_disposition", sa.String(80), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "dataset_id", "dataset_version", "code_version"),
    )
    op.create_index("ix_evaluation_runs_tenant_status", "evaluation_runs", ["tenant_id", "status"])

    op.create_table(
        "human_review_cases",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("recommendation_id", sa.Uuid(), nullable=True),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("status", review_status, nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("artifact_lineage", sa.JSON(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        *_identity_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execution_id"], ["agent_executions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_human_review_tenant_status", "human_review_cases", ["tenant_id", "status"])

    op.create_table(
        "human_decisions",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("review_case_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", decision_outcome, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_evidence", sa.JSON(), nullable=False),
        sa.Column("artifact_lineage", sa.JSON(), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_case_id"], ["human_review_cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_human_decisions_case_created", "human_decisions", ["review_case_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("human_decisions")
    op.drop_table("human_review_cases")
    op.drop_table("evaluation_runs")
    op.drop_table("risk_register_entries")
    op.drop_table("governance_artifacts")
    op.drop_column("recommendations", "artifact_lineage")
    op.drop_column("agent_executions", "artifact_lineage")
    for name in (
        "evaluationgatestatus",
        "humandecisionoutcome",
        "humanreviewstatus",
        "risklevel",
        "governanceartifactstatus",
    ):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
