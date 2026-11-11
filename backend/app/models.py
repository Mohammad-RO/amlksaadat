from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(11), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    listings: Mapped[list["Listing"]] = relationship(back_populates="agent")


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("divar_token", name="uq_listings_divar_token"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True, nullable=False)
    divar_url: Mapped[str] = mapped_column(String(500), nullable=False)
    divar_token: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    building_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    structured_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    unique_code: Mapped[str] = mapped_column(String(8), unique=True, index=True, nullable=False)
    image_file_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    image_urls: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    agent: Mapped[Agent] = relationship(back_populates="listings")


class BuyerSession(Base):
    __tablename__ = "buyer_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    step: Mapped[str] = mapped_column(String(20), default="idle", nullable=False)
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bedrooms_or_more: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bedrooms_skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    area_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    price_min: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_max: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    age_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
