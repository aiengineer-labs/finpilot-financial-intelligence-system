"""Add idempotent transaction ingestion and correction lineage."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261016_0002"
down_revision: str | None = "20261016_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    upload_status = sa.Enum(
        "PROCESSING",
        "COMPLETED",
        "COMPLETED_WITH_ERRORS",
        "FAILED",
        name="uploadstatus",
    )
    transaction_kind = sa.Enum("INCOME", "EXPENSE", "TRANSFER", "REFUND", name="transactionkind")
    classification_method = sa.Enum("RULE", "MESH_REQUIRED", "HUMAN", name="classificationmethod")
    op.create_table(
        "transaction_uploads",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("status", upload_status, nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("accepted_rows", sa.Integer(), nullable=False),
        sa.Column("rejected_rows", sa.Integer(), nullable=False),
        sa.Column("duplicate_rows", sa.Integer(), nullable=False),
        sa.Column("column_mapping", sa.JSON(), nullable=False),
        sa.Column("row_errors", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["financial_accounts.id"],
            name="fk_transaction_uploads_account_id_financial_accounts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_transaction_uploads_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transaction_uploads"),
        sa.UniqueConstraint(
            "tenant_id",
            "account_id",
            "content_sha256",
            name="uq_transaction_uploads_tenant_id",
        ),
    )
    op.create_index(
        "ix_transaction_uploads_tenant_created",
        "transaction_uploads",
        ["tenant_id", "created_at"],
    )
    op.create_table(
        "transactions",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("merchant_raw", sa.String(255), nullable=False),
        sa.Column("merchant_normalized", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("external_transaction_id", sa.String(255), nullable=True),
        sa.Column("balance_minor", sa.BigInteger(), nullable=True),
        sa.Column("kind", transaction_kind, nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("classification_method", classification_method, nullable=False),
        sa.Column("classification_confidence_bps", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("is_excluded_from_cashflow", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["financial_accounts.id"],
            name="fk_transactions_account_id_financial_accounts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_transactions_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["transaction_uploads.id"],
            name="fk_transactions_upload_id_transaction_uploads",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transactions"),
        sa.UniqueConstraint(
            "tenant_id", "account_id", "fingerprint", name="uq_transactions_tenant_id"
        ),
    )
    op.create_index("ix_transactions_merchant_normalized", "transactions", ["merchant_normalized"])
    op.create_index("ix_transactions_tenant_category", "transactions", ["tenant_id", "category"])
    op.create_index(
        "ix_transactions_tenant_date", "transactions", ["tenant_id", "transaction_date"]
    )
    op.create_table(
        "classification_corrections",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("corrected_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("previous_category", sa.String(80), nullable=False),
        sa.Column("new_category", sa.String(80), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["corrected_by_user_id"],
            ["users.id"],
            name="fk_classification_corrections_corrected_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_classification_corrections_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_classification_corrections_transaction_id_transactions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_classification_corrections"),
    )
    op.create_index(
        "ix_classification_corrections_tenant",
        "classification_corrections",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("classification_corrections")
    op.drop_table("transactions")
    op.drop_table("transaction_uploads")
