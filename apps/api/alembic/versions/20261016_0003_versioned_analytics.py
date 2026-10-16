"""Add immutable snapshots, forecasts, and scenario branches."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261016_0003"
down_revision: str | None = "20261016_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "calculation_snapshots",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("opening_balance_minor", sa.BigInteger(), nullable=False),
        sa.Column("source_transaction_count", sa.Integer(), nullable=False),
        sa.Column("source_transaction_ids", sa.JSON(), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("anomaly_results", sa.JSON(), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE",
            name="fk_calculation_snapshots_tenant_id_tenants",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["financial_accounts.id"], ondelete="CASCADE",
            name="fk_calculation_snapshots_account_id_financial_accounts",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_calculation_snapshots"),
        sa.UniqueConstraint(
            "tenant_id", "input_sha256", "engine_version",
            name="uq_calculation_snapshots_tenant_id",
        ),
    )
    op.create_index(
        "ix_calculation_snapshots_tenant_created",
        "calculation_snapshots", ["tenant_id", "created_at"],
    )
    op.create_table(
        "recurring_patterns",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("merchant", sa.String(255), nullable=False),
        sa.Column("cadence", sa.String(20), nullable=False),
        sa.Column("period_days", sa.Integer(), nullable=False),
        sa.Column("typical_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("confidence_bps", sa.Integer(), nullable=False),
        sa.Column("last_observed", sa.Date(), nullable=False),
        sa.Column("supporting_transaction_ids", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE",
            name="fk_recurring_patterns_tenant_id_tenants",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["calculation_snapshots.id"], ondelete="CASCADE",
            name="fk_recurring_patterns_snapshot_id_calculation_snapshots",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recurring_patterns"),
    )
    op.create_index(
        "ix_recurring_patterns_tenant_snapshot", "recurring_patterns",
        ["tenant_id", "snapshot_id"],
    )
    op.create_table(
        "forecasts",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("opening_balance_minor", sa.BigInteger(), nullable=False),
        sa.Column("minimum_balance_minor", sa.BigInteger(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE",
            name="fk_forecasts_tenant_id_tenants",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["calculation_snapshots.id"], ondelete="RESTRICT",
            name="fk_forecasts_snapshot_id_calculation_snapshots",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_forecasts"),
        sa.UniqueConstraint(
            "tenant_id", "snapshot_id", "horizon_days", "engine_version",
            name="uq_forecasts_tenant_id",
        ),
    )
    op.create_index("ix_forecasts_tenant_created", "forecasts", ["tenant_id", "created_at"])
    op.create_table(
        "forecast_points",
        sa.Column("forecast_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("balance_minor", sa.BigInteger(), nullable=False),
        sa.Column("recurring_flow_minor", sa.BigInteger(), nullable=False),
        sa.Column("estimated_variable_spend_minor", sa.BigInteger(), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(
            ["forecast_id"], ["forecasts.id"], ondelete="CASCADE",
            name="fk_forecast_points_forecast_id_forecasts",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_forecast_points"),
        sa.UniqueConstraint("forecast_id", "day", name="uq_forecast_points_forecast_id"),
    )
    op.create_index(
        "ix_forecast_points_forecast_day", "forecast_points", ["forecast_id", "day"]
    )
    op.create_table(
        "scenario_runs",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("forecast_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("shocks", sa.JSON(), nullable=False),
        sa.Column("minimum_balance_minor", sa.BigInteger(), nullable=False),
        sa.Column("first_shortfall_date", sa.Date(), nullable=True),
        sa.Column("ending_delta_minor", sa.BigInteger(), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE",
            name="fk_scenario_runs_tenant_id_tenants",
        ),
        sa.ForeignKeyConstraint(
            ["forecast_id"], ["forecasts.id"], ondelete="RESTRICT",
            name="fk_scenario_runs_forecast_id_forecasts",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scenario_runs"),
    )
    op.create_index(
        "ix_scenario_runs_tenant_created", "scenario_runs", ["tenant_id", "created_at"]
    )
    op.create_table(
        "scenario_points",
        sa.Column("scenario_run_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("balance_minor", sa.BigInteger(), nullable=False),
        sa.Column("recurring_flow_minor", sa.BigInteger(), nullable=False),
        sa.Column("estimated_variable_spend_minor", sa.BigInteger(), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(
            ["scenario_run_id"], ["scenario_runs.id"], ondelete="CASCADE",
            name="fk_scenario_points_scenario_run_id_scenario_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scenario_points"),
        sa.UniqueConstraint("scenario_run_id", "day", name="uq_scenario_points_scenario_run_id"),
    )
    op.create_index(
        "ix_scenario_points_run_day", "scenario_points", ["scenario_run_id", "day"]
    )


def downgrade() -> None:
    op.drop_table("scenario_points")
    op.drop_table("scenario_runs")
    op.drop_table("forecast_points")
    op.drop_table("forecasts")
    op.drop_table("recurring_patterns")
    op.drop_table("calculation_snapshots")
