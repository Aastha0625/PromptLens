from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone
from .database import SessionLocal
from . import stats
from .schemas import StatsSummary, TimelineBucket, RequestList, RequestDetail

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
