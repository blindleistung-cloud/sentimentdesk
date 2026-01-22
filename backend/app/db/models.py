# backend/app/db/models.py

import datetime
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Report(Base):
    __tablename__ = "weekly_reports"

    # Core report fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    week_id = Column(String, unique=True, nullable=False, index=True)
    status = Column(String, default="pending", nullable=False)
    raw_text = Column(Text, nullable=False)
    extracted_inputs = Column("extracted_inputs_json", JSONB)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Score fields (1-to-1 relationship)
    valuation_score = Column(Float)
    capex_score = Column(Float)
    risk_score = Column(Float)
    composite_score = Column(Float)
    rule_trace = Column("rule_trace_json", JSONB)

    # Snapshots relationship (1-to-many)
    snapshots = relationship("MarketDataSnapshot", back_populates="report")

    def __repr__(self):
        return f"<Report(week_id='{self.week_id}', status='{self.status}')>"


class MarketDataSnapshot(Base):
    __tablename__ = "market_data_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("weekly_reports.id"), nullable=False)
    provider = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    as_of_date = Column(DateTime)
    payload = Column("payload_json", JSONB)
    cache_key = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    report = relationship("Report", back_populates="snapshots")

    def __repr__(self):
        return f"<MarketDataSnapshot(provider='{self.provider}', symbol='{self.symbol}')>"

