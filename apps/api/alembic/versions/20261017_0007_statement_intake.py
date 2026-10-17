"""Add format and parser provenance to transaction uploads."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_0007"
down_revision: str | None = "20261016_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transaction_uploads",
        sa.Column("source_format", sa.String(12), nullable=False, server_default="csv"),
    )
    op.add_column(
        "transaction_uploads", sa.Column("claimed_content_type", sa.String(120), nullable=True)
    )
    op.add_column(
        "transaction_uploads",
        sa.Column("detected_content_type", sa.String(120), nullable=False, server_default="text/csv"),
    )
    op.add_column(
        "transaction_uploads",
        sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "transaction_uploads",
        sa.Column("parser_name", sa.String(80), nullable=False, server_default="python-csv"),
    )
    op.add_column(
        "transaction_uploads",
        sa.Column("parser_version", sa.String(40), nullable=False, server_default="1"),
    )
    op.add_column(
        "transaction_uploads",
        sa.Column(
            "extraction_method",
            sa.String(40),
            nullable=False,
            server_default="structured_text",
        ),
    )
    op.add_column("transaction_uploads", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column(
        "transaction_uploads",
        sa.Column("warnings", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "transaction_uploads",
        sa.Column("processing_duration_ms", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "transactions",
        sa.Column("source_evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("transactions", "source_evidence")
    for column in (
        "processing_duration_ms",
        "warnings",
        "page_count",
        "extraction_method",
        "parser_version",
        "parser_name",
        "byte_size",
        "detected_content_type",
        "claimed_content_type",
        "source_format",
    ):
        op.drop_column("transaction_uploads", column)
