"""Store deterministic spending summaries and allow snapshot-grounded advice."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_0009"
down_revision: str | None = "20261017_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "calculation_snapshots", sa.Column("spending_summary", sa.JSON(), nullable=True)
    )
    with op.batch_alter_table("agent_executions") as batch_op:
        batch_op.alter_column("forecast_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    # Advice runs are audit records; refuse to downgrade rather than delete them.
    remaining = op.get_bind().scalar(
        sa.text("SELECT COUNT(*) FROM agent_executions WHERE forecast_id IS NULL")
    )
    if remaining:
        raise RuntimeError(
            f"{remaining} snapshot-grounded advice runs exist; older versions cannot hold them"
        )
    with op.batch_alter_table("agent_executions") as batch_op:
        batch_op.alter_column("forecast_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("calculation_snapshots", "spending_summary")
