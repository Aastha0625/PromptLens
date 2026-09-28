from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc, and_
from typing import Optional
from datetime import datetime, timedelta
from .models import RequestLog
from .schemas import StatsSummary, TimelineBucket, RequestList, RequestItem, RequestDetail

def apply_date_filters(query, from_dt: Optional[datetime], to_dt: Optional[datetime]):
    if from_dt:
        query = query.filter(RequestLog.created_at >= from_dt)
    if to_dt:
        query = query.filter(RequestLog.created_at <= to_dt)
    return query

def get_summary(db: Session, from_dt: Optional[datetime] = None, to_dt: Optional[datetime] = None, provider: Optional[str] = None) -> StatsSummary:
    q = db.query(
        func.count(RequestLog.id).label("total_requests"),
        func.sum(case((and_(RequestLog.status_code >= 200, RequestLog.status_code < 300), 1), else_=0)).label("successful_requests"),
        func.sum(case((and_(RequestLog.status_code >= 200, RequestLog.status_code < 300), 0), else_=1)).label("failed_requests"),
        func.sum(RequestLog.input_tokens).label("total_input_tokens"),
        func.sum(RequestLog.output_tokens).label("total_output_tokens"),
        func.sum(RequestLog.total_tokens).label("total_tokens"),
        func.sum(RequestLog.cost_usd).label("total_cost_usd"),
        func.avg(case((and_(RequestLog.status_code >= 200, RequestLog.status_code < 300), RequestLog.latency_ms))).label("avg_latency_ms"),
        func.sum(case((RequestLog.cost_usd.is_(None), 1), else_=0)).label("unpriced_requests")
    )
    q = apply_date_filters(q, from_dt, to_dt)
    if provider:
        q = q.filter(RequestLog.provider == provider)
    
    res = q.one()
    return StatsSummary(
        total_requests=res.total_requests or 0,
        successful_requests=res.successful_requests or 0,
        failed_requests=res.failed_requests or 0,
        total_input_tokens=res.total_input_tokens or 0,
        total_output_tokens=res.total_output_tokens or 0,
        total_tokens=res.total_tokens or 0,
        total_cost_usd=res.total_cost_usd or 0.0,
        avg_latency_ms=res.avg_latency_ms or 0.0,
        unpriced_requests=res.unpriced_requests or 0
    )

def get_timeline(db: Session, from_dt: datetime, to_dt: datetime, provider: Optional[str] = None, bucket: str = "day") -> list[TimelineBucket]:
    # We use SQLite strftime to group time buckets.
    # Zero-filling is done in Python for database neutrality/simplicity
    format_str = '%Y-%m-%d' if bucket == 'day' else '%Y-%m-%d %H:00:00'
    
    q = db.query(
        func.strftime(format_str, RequestLog.created_at).label("bucket_start"),
        func.count(RequestLog.id).label("requests"),
        func.sum(RequestLog.total_tokens).label("total_tokens"),
        func.sum(RequestLog.cost_usd).label("cost_usd")
    )
    q = apply_date_filters(q, from_dt, to_dt)
    if provider:
        q = q.filter(RequestLog.provider == provider)
    
    q = q.group_by("bucket_start").order_by("bucket_start")
    rows = q.all()
    
    db_data = {row.bucket_start: row for row in rows if row.bucket_start}
    
    result = []
    current = from_dt
    while current <= to_dt:
        if bucket == 'day':
            key = current.strftime('%Y-%m-%d')
            next_dt = current + timedelta(days=1)
        else:
            key = current.strftime('%Y-%m-%d %H:00:00')
            next_dt = current + timedelta(hours=1)
            
        if key in db_data:
            row = db_data[key]
            result.append(TimelineBucket(
                bucket_start=key,
                requests=row.requests or 0,
                total_tokens=row.total_tokens or 0,
                cost_usd=row.cost_usd or 0.0
            ))
        else:
            result.append(TimelineBucket(
                bucket_start=key,
                requests=0,
                total_tokens=0,
                cost_usd=0.0
            ))
        current = next_dt
        
    return result

def get_requests(db: Session, page: int = 1, page_size: int = 20, provider: Optional[str] = None, model: Optional[str] = None, status: Optional[str] = None, from_dt: Optional[datetime] = None, to_dt: Optional[datetime] = None) -> RequestList:
    q = db.query(RequestLog)
    q = apply_date_filters(q, from_dt, to_dt)
    if provider:
        q = q.filter(RequestLog.provider == provider)
    if model:
        q = q.filter(RequestLog.model == model)
    if status == "ok":
        q = q.filter(and_(RequestLog.status_code >= 200, RequestLog.status_code < 300))
    elif status == "error":
        q = q.filter(RequestLog.status_code >= 400)
        
    total = q.count()
    
    q = q.order_by(desc(RequestLog.created_at))
    q = q.offset((page - 1) * page_size).limit(page_size)
    
    items = []
    for r in q.all():
        preview = None
        if r.prompt_text:
            preview = r.prompt_text[:200]
            
        items.append(RequestItem(
            id=r.id,
            created_at=r.created_at,
            provider=r.provider,
            model=r.model,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            total_tokens=r.total_tokens,
            cost_usd=r.cost_usd,
            latency_ms=r.latency_ms,
            status_code=r.status_code,
            prompt_preview=preview,
            is_demo=r.is_demo
        ))
        
    return RequestList(items=items, page=page, page_size=page_size, total=total)

def get_request_by_id(db: Session, req_id: int) -> Optional[RequestDetail]:
    r = db.query(RequestLog).filter(RequestLog.id == req_id).first()
    if not r:
        return None
    return RequestDetail.model_validate(r)
