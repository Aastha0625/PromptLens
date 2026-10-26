import json
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime, timezone

from .database import SessionLocal
from . import stats
from .models import RequestLog, PromptFlag, PromptAnalysis, Suggestion, OptimizerUsage
from .schemas import (
    StatsSummary,
    TimelineBucket,
    RequestList,
    RequestDetail,
    AnalyzeResponse,
    FlagItem,
    FlagList,
    FlagSummary,
    SuggestionItem,
    SuggestionList,
    SuggestionsSummary,
)
from .analysis_service import run_analysis
from .suggestion_service import get_or_create_suggestion

router = APIRouter(prefix="/api", tags=["api"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def ensure_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if not dt:
        return None
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

def validate_date_range(from_dt: Optional[datetime], to_dt: Optional[datetime]):
    if from_dt and to_dt and from_dt > to_dt:
        raise HTTPException(status_code=422, detail="'from' date must be before or equal to 'to' date")

@router.get("/stats/summary", response_model=StatsSummary)
def get_summary(
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    provider: Optional[str] = None,
    db: Session = Depends(get_db)
):
    from_dt = ensure_naive_utc(from_dt)
    to_dt = ensure_naive_utc(to_dt)
    validate_date_range(from_dt, to_dt)
    return stats.get_summary(db, from_dt, to_dt, provider)

@router.get("/stats/timeline", response_model=list[TimelineBucket])
def get_timeline(
    from_dt: datetime = Query(..., alias="from"),
    to_dt: datetime = Query(..., alias="to"),
    provider: Optional[str] = None,
    bucket: str = Query("day"),
    db: Session = Depends(get_db)
):
    if bucket not in ["day", "hour"]:
        raise HTTPException(status_code=422, detail="bucket must be 'day' or 'hour'")
        
    from_dt = ensure_naive_utc(from_dt)
    to_dt = ensure_naive_utc(to_dt)
    validate_date_range(from_dt, to_dt)
    
    return stats.get_timeline(db, from_dt, to_dt, provider, bucket)

@router.get("/requests", response_model=RequestList)
def get_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    provider: Optional[str] = None,
    model: Optional[str] = None,
    req_status: Optional[str] = Query(None, alias="status"),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    db: Session = Depends(get_db)
):
    if req_status and req_status not in ["ok", "error"]:
        raise HTTPException(status_code=422, detail="status must be 'ok' or 'error'")
        
    from_dt = ensure_naive_utc(from_dt)
    to_dt = ensure_naive_utc(to_dt)
    validate_date_range(from_dt, to_dt)
    
    return stats.get_requests(db, page, page_size, provider, model, req_status, from_dt, to_dt)

@router.get("/requests/{id}", response_model=RequestDetail)
def get_request_by_id(id: int, db: Session = Depends(get_db)):
    r = stats.get_request_by_id(db, id)
    if not r:
        raise HTTPException(status_code=404, detail="Request not found")
    return r

# ==================== Phase 4 Analysis Endpoints ====================

@router.post("/analyze", response_model=AnalyzeResponse)
def trigger_analysis(
    limit: Optional[int] = Query(None, ge=1),
    reanalyze: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Triggers batch analysis for logged prompts.
    Does not run on proxy path; executed on demand.
    """
    result = run_analysis(db, limit=limit, reanalyze=reanalyze)
    return result

@router.get("/flags", response_model=FlagList)
def get_flags(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    flag_type: Optional[str] = None,
    severity: Optional[str] = None,
    provider: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Returns paginated list of flags joined with their respective request context.
    """
    query = db.query(PromptFlag, RequestLog).join(RequestLog, PromptFlag.request_id == RequestLog.id)

    if flag_type:
        query = query.filter(PromptFlag.flag_type == flag_type)
    if severity:
        query = query.filter(PromptFlag.severity == severity)
    if provider:
        query = query.filter(RequestLog.provider == provider)

    total = query.count()
    rows = query.order_by(PromptFlag.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for flag, req in rows:
        preview = (req.prompt_text or "").replace("\n", " ").strip()
        if len(preview) > 100:
            preview = preview[:97] + "..."

        items.append(FlagItem(
            id=flag.id,
            request_id=flag.request_id,
            flag_type=flag.flag_type,
            severity=flag.severity,
            detail=flag.detail,
            created_at=flag.created_at,
            provider=req.provider,
            model=req.model,
            input_tokens=req.input_tokens,
            prompt_preview=preview,
        ))

    return FlagList(items=items, page=page, page_size=page_size, total=total)

@router.get("/flags/summary", response_model=FlagSummary)
def get_flags_summary(db: Session = Depends(get_db)):
    """
    Returns aggregate summary of prompt analysis results:
    analyzed counts, breakdown by type/severity, and estimated wasted tokens.
    """
    analyzed_requests = db.query(func.count(PromptAnalysis.request_id)).scalar() or 0
    flagged_requests = db.query(func.count(func.distinct(PromptFlag.request_id))).scalar() or 0
    total_flags = db.query(func.count(PromptFlag.id)).scalar() or 0

    # Counts by flag type
    by_type_rows = db.query(PromptFlag.flag_type, func.count(PromptFlag.id)).group_by(PromptFlag.flag_type).all()
    by_type = {row[0]: row[1] for row in by_type_rows}

    # Counts by severity
    by_sev_rows = db.query(PromptFlag.severity, func.count(PromptFlag.id)).group_by(PromptFlag.severity).all()
    by_severity = {row[0]: row[1] for row in by_sev_rows}

    # Sum of estimated wasted tokens across all flags
    flags = db.query(PromptFlag.detail).all()
    total_wasted = 0
    for (detail_str,) in flags:
        try:
            data = json.loads(detail_str)
            wasted = data.get("total_estimated_wasted_tokens") or data.get("estimated_wasted_tokens") or 0
            total_wasted += int(wasted)
        except Exception:
            pass

    return FlagSummary(
        analyzed_requests=analyzed_requests,
        flagged_requests=flagged_requests,
        total_flags=total_flags,
        by_type=by_type,
        by_severity=by_severity,
        total_estimated_wasted_tokens=total_wasted,
    )

# ==================== Phase 5 Suggestion Endpoints ====================

@router.post("/suggest/{flag_id}", response_model=SuggestionItem)
def generate_suggestion(
    flag_id: int,
    regenerate: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Generates or fetches a prompt rewrite suggestion for the given flag_id.
    - Tier 1 (redundant/repeated): Rule-based deterministic rewrite.
    - Tier 2 (verbose): LLM rewrite with semantic verification (behind ENABLE_LLM_REWRITE).
    Idempotent: Returns existing suggestion if already 'ok' or 'not_verified_safe'.
    """
    suggestion = get_or_create_suggestion(db, flag_id=flag_id, regenerate=regenerate)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Prompt flag not found")
    return suggestion

@router.get("/suggestions", response_model=SuggestionList)
def get_suggestions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    method: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Returns paginated list of suggestions ordered newest first.
    """
    if method and method not in ["rule_based", "llm_rewrite"]:
        raise HTTPException(status_code=422, detail="method must be 'rule_based' or 'llm_rewrite'")

    valid_statuses = ["ok", "not_verified_safe", "disabled", "failed", "no_change"]
    if status and status not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"status must be one of {valid_statuses}")

    query = db.query(Suggestion)
    if method:
        query = query.filter(Suggestion.method == method)
    if status:
        query = query.filter(Suggestion.status == status)

    total = query.count()
    items = query.order_by(Suggestion.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return SuggestionList(items=items, page=page, page_size=page_size, total=total)

@router.get("/suggestions/summary", response_model=SuggestionsSummary)
def get_suggestions_summary(db: Session = Depends(get_db)):
    """
    Returns aggregate summary of suggestions: counts by method/status,
    separate rule-based and verified LLM savings, and total optimizer runtime cost.
    """
    total_suggestions = db.query(func.count(Suggestion.id)).scalar() or 0

    # Counts by method
    method_rows = db.query(Suggestion.method, func.count(Suggestion.id)).group_by(Suggestion.method).all()
    by_method = {row[0]: row[1] for row in method_rows}

    # Counts by status
    status_rows = db.query(Suggestion.status, func.count(Suggestion.id)).group_by(Suggestion.status).all()
    by_status = {row[0]: row[1] for row in status_rows}

    # Verified counts for LLM rewrites
    verified_count = db.query(func.count(Suggestion.id)).filter(
        Suggestion.method == "llm_rewrite",
        Suggestion.status == "ok",
    ).scalar() or 0

    not_verified_safe_count = db.query(func.count(Suggestion.id)).filter(
        Suggestion.method == "llm_rewrite",
        Suggestion.status == "not_verified_safe",
    ).scalar() or 0

    # Savings: count savings only from usable suggestions (Change 5)
    rule_based_savings = db.query(func.sum(Suggestion.estimated_token_savings)).filter(
        Suggestion.method == "rule_based",
        Suggestion.status == "ok",
    ).scalar() or 0

    verified_llm_savings = db.query(func.sum(Suggestion.estimated_token_savings)).filter(
        Suggestion.method == "llm_rewrite",
        Suggestion.status == "ok",
    ).scalar() or 0

    total_savings = rule_based_savings + verified_llm_savings

    # Optimizer total cost (overhead tracking)
    optimizer_total_cost_usd = db.query(func.sum(OptimizerUsage.cost_usd)).scalar() or 0.0

    return SuggestionsSummary(
        total_suggestions=total_suggestions,
        by_method=by_method,
        by_status=by_status,
        verified_count=verified_count,
        not_verified_safe_count=not_verified_safe_count,
        rule_based_savings=int(rule_based_savings),
        verified_llm_savings=int(verified_llm_savings),
        total_estimated_token_savings=int(total_savings),
        optimizer_total_cost_usd=round(float(optimizer_total_cost_usd), 4),
    )

