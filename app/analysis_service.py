import time
import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from .models import RequestLog, PromptFlag, PromptAnalysis, utc_now
from .analyzer_config import (
    ANALYZER_VERSION,
    VERBOSE_GROUP_MIN_SIZE,
    VERBOSE_SEVERITY_HIGH_RATIO,
    VERBOSE_SEVERITY_MEDIUM_RATIO,
)
from .analyzer import analyze_prompt, extract_template_key
from .embedder import Embedder

logger = logging.getLogger(__name__)

def get_template_group_stats(db: Session, min_group_size: int = VERBOSE_GROUP_MIN_SIZE) -> Dict[tuple, Dict[str, Any]]:
    """
    Executes a single SQL GROUP BY query across ALL rows in `requests`
    to compute minimum input tokens and counts for each (provider, model, template_key).
    Uses the custom SQLite function `template_key` registered in database.py.
    """
    query = text("""
        SELECT 
            provider, 
            model, 
            template_key(prompt_text) AS tkey, 
            COUNT(*) AS cnt, 
            MIN(input_tokens) AS min_tokens
        FROM requests
        WHERE status_code >= 200 
          AND status_code < 300 
          AND prompt_text IS NOT NULL 
          AND trim(prompt_text) != ''
          AND input_tokens IS NOT NULL 
          AND input_tokens > 0
        GROUP BY provider, model, tkey
        HAVING COUNT(*) >= :min_size
    """)

    results = db.execute(query, {"min_size": min_group_size}).fetchall()
    group_stats = {}
    for row in results:
        key = (row.provider, row.model, row.tkey)
        group_stats[key] = {
            "count": row.cnt,
            "min_tokens": row.min_tokens,
        }
    return group_stats

def run_analysis(
    db: Session,
    limit: Optional[int] = None,
    reanalyze: bool = False,
    embedder: Optional[Embedder] = None,
    batch_size: int = 50,
) -> Dict[str, Any]:
    """
    Runs batch prompt analysis on eligible request logs:
    1. Fetches requests in batches of 50.
    2. Idempotently cleans old flags per request right before creating new ones.
    3. Runs redundancy and repeated content checks.
    4. Runs global template verbosity check across all rows via SQL GROUP BY.
    5. Saves PromptFlag and PromptAnalysis records.
    """
    start_time = time.time()

    if embedder is None:
        embedder = Embedder.get_instance()

    # Base query: 200-299 status code and non-empty prompt_text
    query = db.query(RequestLog).filter(
        RequestLog.status_code >= 200,
        RequestLog.status_code < 300,
        RequestLog.prompt_text.isnot(None),
        RequestLog.prompt_text != "",
    )

    if not reanalyze:
        # Exclude already-analyzed requests
        analyzed_subquery = db.query(PromptAnalysis.request_id)
        query = query.filter(~RequestLog.id.in_(analyzed_subquery))

    query = query.order_by(RequestLog.id.asc())

    if limit is not None and limit > 0:
        query = query.limit(limit)

    all_target_requests = query.all()
    if not all_target_requests:
        return {
            "requests_analyzed": 0,
            "requests_flagged": 0,
            "flags_created": 0,
            "semantic_check_ran": embedder.is_available() if embedder else False,
            "duration_ms": round((time.time() - start_time) * 1000, 2),
        }

    total_analyzed = len(all_target_requests)
    analyzed_request_ids = [req.id for req in all_target_requests]
    flags_by_request: Dict[int, List[PromptFlag]] = {req.id: [] for req in all_target_requests}
    semantic_check_ran = False

    # Process in batches of 50 for local prompt checks (redundancy & repeated content)
    for i in range(0, total_analyzed, batch_size):
        batch = all_target_requests[i : i + batch_size]
        for req in batch:
            # Idempotency: Delete old flags and analysis for this request right before writing new ones
            db.query(PromptFlag).filter(PromptFlag.request_id == req.id).delete()
            db.query(PromptAnalysis).filter(PromptAnalysis.request_id == req.id).delete()

            # Analyze single prompt
            tokens = req.input_tokens or req.total_tokens
            flags_data, sem_ran = analyze_prompt(req.prompt_text, tokens, embedder)
            if sem_ran:
                semantic_check_ran = True

            for fd in flags_data:
                flag = PromptFlag(
                    request_id=req.id,
                    flag_type=fd["flag_type"],
                    severity=fd["severity"],
                    detail=fd["detail"],
                    analyzer_version=fd["analyzer_version"],
                    created_at=utc_now(),
                )
                flags_by_request[req.id].append(flag)

        db.flush()

    # Global verbose_for_template check:
    # Query across ALL rows in `requests` (any batch, analyzed or not)
    template_groups = get_template_group_stats(db, min_group_size=VERBOSE_GROUP_MIN_SIZE)

    for req in all_target_requests:
        if not req.input_tokens or req.input_tokens <= 0:
            continue

        tkey = extract_template_key(req.prompt_text)
        group_key = (req.provider, req.model, tkey)
        group = template_groups.get(group_key)

        if not group or group["count"] < VERBOSE_GROUP_MIN_SIZE:
            continue

        min_tokens = group["min_tokens"]
        if min_tokens <= 0:
            continue

        ratio = req.input_tokens / min_tokens
        if ratio >= VERBOSE_SEVERITY_MEDIUM_RATIO:
            severity = "high" if ratio >= VERBOSE_SEVERITY_HIGH_RATIO else "medium"
            wasted = req.input_tokens - min_tokens
            detail = {
                "template_key": tkey,
                "group_size": group["count"],
                "min_input_tokens": min_tokens,
                "request_input_tokens": req.input_tokens,
                "ratio": round(ratio, 2),
                "estimated_wasted_tokens": wasted,
            }
            vflag = PromptFlag(
                request_id=req.id,
                flag_type="verbose_for_template",
                severity=severity,
                detail=json.dumps(detail),
                analyzer_version=ANALYZER_VERSION,
                created_at=utc_now(),
            )
            flags_by_request[req.id].append(vflag)

    # Persist all flags and analysis rows
    total_flags = 0
    flagged_requests_count = 0

    for req in all_target_requests:
        req_flags = flags_by_request[req.id]
        if req_flags:
            flagged_requests_count += 1
            total_flags += len(req_flags)
            db.add_all(req_flags)

        # Create PromptAnalysis row
        analysis_record = PromptAnalysis(
            request_id=req.id,
            analyzed_at=utc_now(),
            analyzer_version=ANALYZER_VERSION,
            flag_count=len(req_flags),
        )
        db.add(analysis_record)

    db.commit()

    duration_ms = round((time.time() - start_time) * 1000, 2)
    return {
        "requests_analyzed": total_analyzed,
        "requests_flagged": flagged_requests_count,
        "flags_created": total_flags,
        "semantic_check_ran": semantic_check_ran,
        "duration_ms": duration_ms,
    }
