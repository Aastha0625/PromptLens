from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, Index
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

    __table_args__ = (
        Index('ix_requests_provider_model', 'provider', 'model'),
    )
