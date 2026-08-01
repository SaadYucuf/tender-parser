from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    tender_number: Mapped[str | None] = mapped_column(String(255), index=True)
    lot_number: Mapped[str | None] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(Text)
    lot_name: Mapped[str | None] = mapped_column(Text)
    customer: Mapped[str | None] = mapped_column(Text)
    customer_region: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(80), index=True)
    amount: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(16))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str | None] = mapped_column(String(80), index=True)
    language: Mapped[str | None] = mapped_column(String(16))
    relevance_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    required_documents: Mapped[str | None] = mapped_column(Text)
    bid_security: Mapped[str | None] = mapped_column(Text)
    manufacturer_authorization: Mapped[str | None] = mapped_column(Text)
    delivery_requirements: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    sources: Mapped[list["TenderSource"]] = relationship(back_populates="tender", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="tender", cascade="all, delete-orphan")
    user_actions: Mapped[list["UserAction"]] = relationship(back_populates="tender", cascade="all, delete-orphan")


class TenderSource(Base):
    __tablename__ = "tender_sources"
    __table_args__ = (UniqueConstraint("source_name", "external_id", "source_url", name="uq_tender_source_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), index=True)
    source_name: Mapped[str] = mapped_column(String(100), index=True)
    source_url: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)

    tender: Mapped[Tender] = relationship(back_populates="sources")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), index=True)
    notification_type: Mapped[str] = mapped_column(String(50), index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    telegram_chat_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)

    tender: Mapped[Tender] = relationship(back_populates="notifications")


class SourceRun(Base):
    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(100), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_found: Mapped[int] = mapped_column(Integer, default=0)
    new_records: Mapped[int] = mapped_column(Integer, default=0)
    updated_records: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_records: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="running")
    error_message: Mapped[str | None] = mapped_column(Text)


class UserAction(Base):
    __tablename__ = "user_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    chat_id: Mapped[str] = mapped_column(String(255), index=True)
    tender_id: Mapped[int | None] = mapped_column(ForeignKey("tenders.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tender: Mapped[Tender | None] = relationship(back_populates="user_actions")
