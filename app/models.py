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
    suggestions = relationship("Suggestion", back_populates="request", cascade="all, delete-orphan")

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
    suggestion = relationship("Suggestion", back_populates="flag", uselist=False, cascade="all, delete-orphan")

class PromptAnalysis(Base):
    __tablename__ = "prompt_analysis"

    request_id = Column(Integer, ForeignKey("requests.id"), primary_key=True)
    analyzed_at = Column(DateTime, default=utc_now)
    analyzer_version = Column(Integer, nullable=False)
    flag_count = Column(Integer, nullable=False, default=0)

    request = relationship("RequestLog", back_populates="analysis")

class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True, index=True)
    flag_id = Column(Integer, ForeignKey("prompt_flags.id"), unique=True, nullable=False, index=True)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=False, index=True)
    method = Column(String, nullable=False)  # "rule_based" or "llm_rewrite"
    original_prompt_excerpt = Column(String(200), nullable=False)
    rewritten_prompt = Column(Text, nullable=True)  # Nullable as per change 4
    message = Column(Text, nullable=True)  # Nullable message for disabled/failed/no_change text as per change 4
    estimated_token_savings = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False)  # "ok", "not_verified_safe", "disabled", "failed", "no_change"
    similarity_score = Column(Float, nullable=True)
    optimizer_provider = Column(String, nullable=True)
    optimizer_model = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    flag = relationship("PromptFlag", back_populates="suggestion")
    request = relationship("RequestLog", back_populates="suggestions")
    usage_records = relationship("OptimizerUsage", back_populates="suggestion", cascade="all, delete-orphan")

class OptimizerUsage(Base):
    __tablename__ = "optimizer_usage"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=utc_now)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String, nullable=False)  # "rewrite" or "verify"
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=True)

    suggestion = relationship("Suggestion", back_populates="usage_records")
