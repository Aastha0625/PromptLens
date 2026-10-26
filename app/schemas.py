from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

class NormalizedLog(BaseModel):
    provider: str
    model: str
    prompt_text: Optional[str] = None
    reply_text: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None
    error: Optional[str] = None

class StatsSummary(BaseModel):
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0
    unpriced_requests: int = 0

class TimelineBucket(BaseModel):
    bucket_start: str
    requests: int
    total_tokens: int
    cost_usd: float

class RequestItem(BaseModel):
    id: int
    created_at: datetime
    provider: str
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None
    prompt_preview: Optional[str] = None
    is_demo: bool
    
    model_config = {"from_attributes": True}

class RequestList(BaseModel):
    items: List[RequestItem]
    page: int
    page_size: int
    total: int

class RequestDetail(BaseModel):
    id: int
    created_at: datetime
    provider: str
    model: str
    prompt_text: Optional[str] = None
    reply_text: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None
    error: Optional[str] = None
    is_demo: bool
    
    model_config = {"from_attributes": True}

class AnalyzeResponse(BaseModel):
    requests_analyzed: int
    requests_flagged: int
    flags_created: int
    semantic_check_ran: bool
    duration_ms: float

class FlagItem(BaseModel):
    id: int
    request_id: int
    flag_type: str
    severity: str
    detail: str
    created_at: datetime
    provider: str
    model: str
    input_tokens: Optional[int] = None
    prompt_preview: Optional[str] = None

    model_config = {"from_attributes": True}

class FlagList(BaseModel):
    items: List[FlagItem]
    page: int
    page_size: int
    total: int

class FlagSummary(BaseModel):
    analyzed_requests: int
    flagged_requests: int
    total_flags: int
    by_type: Dict[str, int]
    by_severity: Dict[str, int]
    total_estimated_wasted_tokens: int
