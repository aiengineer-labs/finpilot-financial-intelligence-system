"""Add account semantics and balance-free spending snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_0008"
down_revision: str | None = "20261017_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    account_type = sa.Enum("UNKNOWN", "DEPOSIT", "CREDIT_CARD", name="accounttype")
    account_type.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "financial_accounts",
        sa.Column(
            "account_type",
            account_type,
            nullable=False,
            server_default="UNKNOWN",
        ),
    )
    op.execute(
        """
        UPDATE financial_accounts
        SET account_type = 'DEPOSIT'
        WHERE EXISTS (
            SELECT 1 FROM transactions
            WHERE transactions.account_id = financial_accounts.id
              AND transactions.balance_minor IS NOT NULL
        )
        """
    )
    op.add_column(
        "transaction_uploads",
        sa.Column("statement_kind", sa.String(20), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "calculation_snapshots",
        sa.Column("analysis_mode", sa.String(20), nullable=False, server_default="cashflow"),
    )
    with op.batch_alter_table("calculation_snapshots") as batch_op:
        batch_op.alter_column(
            "opening_balance_minor",
            existing_type=sa.BigInteger(),
            nullable=True,
        )


def downgrade() -> None:
    # Old application versions cannot represent balance-free snapshots.
    op.execute("DELETE FROM calculation_snapshots WHERE opening_balance_minor IS NULL")
    with op.batch_alter_table("calculation_snapshots") as batch_op:
        batch_op.alter_column(
            "opening_balance_minor",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
    op.drop_column("calculation_snapshots", "analysis_mode")
    op.drop_column("transaction_uploads", "statement_kind")
    op.drop_column("financial_accounts", "account_type")
    sa.Enum(name="accounttype").drop(op.get_bind(), checkfirst=True)
