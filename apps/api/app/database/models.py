from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TenantRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"
    REVIEWER = "reviewer"


class UploadStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class TransactionKind(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    REFUND = "refund"


class ClassificationMethod(StrEnum):
    RULE = "rule"
    MESH_REQUIRED = "mesh_required"
    HUMAN = "human"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    memberships: Mapped[list["Membership"]] = relationship(back_populates="tenant")
    accounts: Mapped[list["FinancialAccount"]] = relationship(back_populates="tenant")
    uploads: Mapped[list["TransactionUpload"]] = relationship(back_populates="tenant")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="tenant")


class Membership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    role: Mapped[TenantRole] = mapped_column(Enum(TenantRole), default=TenantRole.MEMBER)
    user: Mapped[User] = relationship(back_populates="memberships")
    tenant: Mapped[Tenant] = relationship(back_populates="memberships")


class FinancialAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_reference"),
        Index("ix_financial_accounts_tenant_id_id", "tenant_id", "id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    external_reference: Mapped[str] = mapped_column(String(128))
    tenant: Mapped[Tenant] = relationship(back_populates="accounts")
    uploads: Mapped[list["TransactionUpload"]] = relationship(back_populates="account")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")


class TransactionUpload(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transaction_uploads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_id", "content_sha256"),
        Index("ix_transaction_uploads_tenant_created", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[UploadStatus] = mapped_column(Enum(UploadStatus))
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    accepted_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)
    column_mapping: Mapped[dict[str, str | None]] = mapped_column(JSON)
    row_errors: Mapped[list[dict[str, str | int]]] = mapped_column(JSON, default=list)
    tenant: Mapped[Tenant] = relationship(back_populates="uploads")
    account: Mapped[FinancialAccount] = relationship(back_populates="uploads")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="upload")


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_id", "fingerprint"),
        Index("ix_transactions_tenant_date", "tenant_id", "transaction_date"),
        Index("ix_transactions_tenant_category", "tenant_id", "category"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="CASCADE")
    )
    upload_id: Mapped[UUID] = mapped_column(
        ForeignKey("transaction_uploads.id", ondelete="RESTRICT")
    )
    transaction_date: Mapped[date] = mapped_column(Date)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    merchant_raw: Mapped[str] = mapped_column(String(255))
    merchant_normalized: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    external_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    balance_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    kind: Mapped[TransactionKind] = mapped_column(Enum(TransactionKind))
    category: Mapped[str] = mapped_column(String(80))
    classification_method: Mapped[ClassificationMethod] = mapped_column(Enum(ClassificationMethod))
    classification_confidence_bps: Mapped[int] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(64))
    is_excluded_from_cashflow: Mapped[bool] = mapped_column(Boolean, default=False)
    tenant: Mapped[Tenant] = relationship(back_populates="transactions")
    account: Mapped[FinancialAccount] = relationship(back_populates="transactions")
    upload: Mapped[TransactionUpload] = relationship(back_populates="transactions")
    corrections: Mapped[list["ClassificationCorrection"]] = relationship(
        back_populates="transaction"
    )


class ClassificationCorrection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "classification_corrections"
    __table_args__ = (Index("ix_classification_corrections_tenant", "tenant_id", "created_at"),)

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    transaction_id: Mapped[UUID] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"))
    corrected_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    previous_category: Mapped[str] = mapped_column(String(80))
    new_category: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(500))
    transaction: Mapped[Transaction] = relationship(back_populates="corrections")
