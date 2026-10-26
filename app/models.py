from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, Index, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .database import Base

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class RequestLog(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=utc_now, index=True)
    provider = Column(String, index=True)
    model = Column(String, index=True)
    prompt_text = Column(Text, nullable=True)
    reply_text = Column(Text, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=True)
    status_code = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    is_demo = Column(Boolean, default=False, nullable=False)

    flags = relationship("PromptFlag", back_populates="request", cascade="all, delete-orphan")
    analysis = relationship("PromptAnalysis", back_populates="request", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_requests_provider_model', 'provider', 'model'),
    )

class PromptFlag(Base):
    __tablename__ = "prompt_flags"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=False, index=True)
    flag_type = Column(String, nullable=False, index=True)
    severity = Column(String, nullable=False)
    detail = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    analyzer_version = Column(Integer, nullable=False)

    request = relationship("RequestLog", back_populates="flags")

class PromptAnalysis(Base):
    __tablename__ = "prompt_analysis"

    request_id = Column(Integer, ForeignKey("requests.id"), primary_key=True)
    analyzed_at = Column(DateTime, default=utc_now)
    analyzer_version = Column(Integer, nullable=False)
    flag_count = Column(Integer, nullable=False, default=0)

    request = relationship("RequestLog", back_populates="analysis")
