"""Record Mesh categorization runs and per-row decisions for ambiguous transactions."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261017_0010"
down_revision: str | None = "20261017_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # A new enum value cannot be used inside the transaction that adds it.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE classificationmethod ADD VALUE IF NOT EXISTS 'MESH'")
    run_status = postgresql.ENUM(
        "RUNNING", "COMPLETED", "REJECTED", "FAILED",
        name="agentrunstatus", create_type=False,
    )
    op.create_table(
        "categorization_runs",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("model_id", sa.String(120), nullable=False),
        sa.Column("rows_pending", sa.Integer(), nullable=False),
        sa.Column("labels_sent", sa.Integer(), nullable=False),
        sa.Column("labels_withheld", sa.Integer(), nullable=False),
        sa.Column("rows_updated", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("artifact_lineage", sa.JSON(), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE",
            name="fk_categorization_runs_tenant_id_tenants",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["financial_accounts.id"], ondelete="CASCADE",
            name="fk_categorization_runs_account_id_financial_accounts",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], ondelete="RESTRICT",
            name="fk_categorization_runs_requested_by_user_id_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_categorization_runs"),
    )
    op.create_index(
        "ix_categorization_runs_tenant_created", "categorization_runs", ["tenant_id", "created_at"]
    )
    op.create_table(
        "categorization_decisions",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("label_id", sa.String(20), nullable=False),
        sa.Column("previous_category", sa.String(80), nullable=False),
        sa.Column("proposed_category", sa.String(80), nullable=False),
        sa.Column("confidence_bps", sa.Integer(), nullable=False),
        sa.Column("applied", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE",
            name="fk_categorization_decisions_tenant_id_tenants",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["categorization_runs.id"], ondelete="CASCADE",
            name="fk_categorization_decisions_run_id_categorization_runs",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="CASCADE",
            name="fk_categorization_decisions_transaction_id_transactions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_categorization_decisions"),
    )
    op.create_index(
        "ix_categorization_decisions_tenant_run",
        "categorization_decisions",
        ["tenant_id", "run_id"],
    )


def downgrade() -> None:
    # Categorization runs are audit records; refuse to downgrade rather than delete them.
    bind = op.get_bind()
    runs = bind.scalar(sa.text("SELECT COUNT(*) FROM categorization_runs"))
    labelled = bind.scalar(
        sa.text("SELECT COUNT(*) FROM transactions WHERE classification_method = 'MESH'")
    )
    if runs or labelled:
        raise RuntimeError(
            f"{runs} categorization runs and {labelled} Mesh-categorized rows exist; "
            "older versions cannot hold them"
        )
    op.drop_index("ix_categorization_decisions_tenant_run", table_name="categorization_decisions")
    op.drop_table("categorization_decisions")
    op.drop_index("ix_categorization_runs_tenant_created", table_name="categorization_runs")
    op.drop_table("categorization_runs")
    # PostgreSQL cannot drop an enum value; the unused 'MESH' label is harmless to older code.
