import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .config import settings
from .models import PromptFlag, RequestLog, Suggestion, OptimizerUsage, utc_now
from .rewriter import apply_rule_based_rewrite
from .optimizer_client import OptimizerClient
from .embedder import Embedder, compute_cosine_similarity
from .cost import calculate_cost

logger = logging.getLogger(__name__)

def get_or_create_suggestion(
    db: Session,
    flag_id: int,
    regenerate: bool = False,
    optimizer_client: Optional[OptimizerClient] = None,
    embedder: Optional[Embedder] = None,
) -> Optional[Suggestion]:
    """
    Generates or fetches a suggestion for the given flag_id.
    - Tier 1: Rule-based for redundant_sentences & repeated_content (zero LLM calls).
    - Tier 2: LLM-based for verbose_for_template (behind ENABLE_LLM_REWRITE).
    Idempotency:
    - If a suggestion exists with status 'ok' or 'not_verified_safe' and not regenerate, returns it.
    - If existing status is 'disabled', 'failed', or 'no_change', retries and updates in place.
    """
    flag = db.query(PromptFlag).filter(PromptFlag.id == flag_id).first()
    if not flag:
        return None

    req = db.query(RequestLog).filter(RequestLog.id == flag.request_id).first()
    if not req or not req.prompt_text:
        return None

    # Check for existing suggestion
    existing = db.query(Suggestion).filter(Suggestion.flag_id == flag_id).first()
    if existing and not regenerate:
        # Idempotency applies only to 'ok' and 'not_verified_safe'
        if existing.status in ["ok", "not_verified_safe"]:
            return existing

    suggestion = existing if existing else Suggestion(flag_id=flag_id, request_id=req.id)
    suggestion.original_prompt_excerpt = req.prompt_text[:200]
    suggestion.created_at = utc_now()

    # ==================== TIER 1: Rule-Based ====================
    if flag.flag_type in ["redundant_sentences", "repeated_content"]:
        rewritten, savings, msg, status = apply_rule_based_rewrite(
            flag_type=flag.flag_type,
            flag_detail_json=flag.detail,
            original_prompt_text=req.prompt_text,
            flag_analyzer_version=flag.analyzer_version,
        )
        suggestion.method = "rule_based"
        suggestion.rewritten_prompt = rewritten
        suggestion.message = msg
        suggestion.estimated_token_savings = savings
        suggestion.status = status
        suggestion.similarity_score = None
        suggestion.optimizer_provider = None
        suggestion.optimizer_model = None

        try:
            if not existing:
                db.add(suggestion)
            db.commit()
            db.refresh(suggestion)
            return suggestion
        except IntegrityError:
            db.rollback()
            return db.query(Suggestion).filter(Suggestion.flag_id == flag_id).first()

    # ==================== TIER 2: LLM-Based ====================
    elif flag.flag_type == "verbose_for_template":
        suggestion.method = "llm_rewrite"

        # Check feature flag
        if not settings.ENABLE_LLM_REWRITE:
            suggestion.rewritten_prompt = None
            suggestion.message = "LLM rewriting is disabled. Set ENABLE_LLM_REWRITE=true to enable."
            suggestion.estimated_token_savings = 0
            suggestion.status = "disabled"
            suggestion.similarity_score = None
            suggestion.optimizer_provider = settings.OPTIMIZER_PROVIDER
            suggestion.optimizer_model = settings.OPTIMIZER_MODEL

            try:
                if not existing:
                    db.add(suggestion)
                db.commit()
                db.refresh(suggestion)
                return suggestion
            except IntegrityError:
                db.rollback()
                return db.query(Suggestion).filter(Suggestion.flag_id == flag_id).first()

        # PREFLIGHT CHECKS (Change 2)
        # 1. Baseline reply_text must exist for verification
        if not req.reply_text or not req.reply_text.strip():
            suggestion.rewritten_prompt = None
            suggestion.message = "Original request has no baseline reply_text for verification."
            suggestion.estimated_token_savings = 0
            suggestion.status = "not_verified_safe"
            suggestion.similarity_score = None
            suggestion.optimizer_provider = settings.OPTIMIZER_PROVIDER
            suggestion.optimizer_model = settings.OPTIMIZER_MODEL

            try:
                if not existing:
                    db.add(suggestion)
                db.commit()
                db.refresh(suggestion)
                return suggestion
            except IntegrityError:
                db.rollback()
                return db.query(Suggestion).filter(Suggestion.flag_id == flag_id).first()

        if embedder is None:
            embedder = Embedder.get_instance()

        # 2. Embedder must be available
        if not embedder.is_available():
            suggestion.rewritten_prompt = None
            suggestion.message = "Semantic embedder is unavailable for verification."
            suggestion.estimated_token_savings = 0
            suggestion.status = "failed"
            suggestion.similarity_score = None
            suggestion.optimizer_provider = settings.OPTIMIZER_PROVIDER
            suggestion.optimizer_model = settings.OPTIMIZER_MODEL

            try:
                if not existing:
                    db.add(suggestion)
                db.commit()
                db.refresh(suggestion)
                return suggestion
            except IntegrityError:
                db.rollback()
                return db.query(Suggestion).filter(Suggestion.flag_id == flag_id).first()

        if optimizer_client is None:
            optimizer_client = OptimizerClient()

        # 3. OPTIMIZER_API_KEY must be configured
        if not optimizer_client.api_key:
            suggestion.rewritten_prompt = None
            suggestion.message = "OPTIMIZER_API_KEY is not configured."
            suggestion.estimated_token_savings = 0
            suggestion.status = "failed"
            suggestion.similarity_score = None
            suggestion.optimizer_provider = optimizer_client.provider
            suggestion.optimizer_model = optimizer_client.model

            try:
                if not existing:
                    db.add(suggestion)
                db.commit()
                db.refresh(suggestion)
                return suggestion
            except IntegrityError:
                db.rollback()
                return db.query(Suggestion).filter(Suggestion.flag_id == flag_id).first()

        # OPTIMIZER CALLS (Outside write transaction)
        new_usages = []

        # Call 1: Generate rewrite
        try:
            rewritten_prompt, usage1 = optimizer_client.generate_rewrite(req.prompt_text)
            cost1 = calculate_cost(usage1["provider"], usage1["model"], usage1.get("input_tokens"), usage1.get("output_tokens"))
            new_usages.append({
                "purpose": "rewrite",
                "provider": usage1["provider"],
                "model": usage1["model"],
                "input_tokens": usage1.get("input_tokens"),
                "output_tokens": usage1.get("output_tokens"),
                "cost_usd": cost1,
                "latency_ms": usage1.get("latency_ms"),
            })
        except Exception as e:
            logger.error("Optimizer rewrite call failed: %s", e)
            suggestion.rewritten_prompt = None
            suggestion.message = f"Optimizer rewrite failed: {str(e)}"
            suggestion.estimated_token_savings = 0
            suggestion.status = "failed"
            suggestion.similarity_score = None
            suggestion.optimizer_provider = optimizer_client.provider
            suggestion.optimizer_model = optimizer_client.model

            try:
                if not existing:
                    db.add(suggestion)
                db.commit()
                db.refresh(suggestion)
                return suggestion
            except IntegrityError:
                db.rollback()
                return db.query(Suggestion).filter(Suggestion.flag_id == flag_id).first()

        # Guard rail: Is rewrite shorter? (Change 8)
        if len(rewritten_prompt) >= len(req.prompt_text):
            suggestion.rewritten_prompt = rewritten_prompt
            suggestion.message = "Rewritten prompt was not shorter than original."
            suggestion.estimated_token_savings = 0
            suggestion.status = "no_change"
            suggestion.similarity_score = None
            suggestion.optimizer_provider = optimizer_client.provider
            suggestion.optimizer_model = optimizer_client.model

            _save_suggestion_and_usages(db, suggestion, existing, new_usages)
            return suggestion

        # Call 2: Generate reply for verification
        try:
            new_reply, usage2 = optimizer_client.generate_reply(rewritten_prompt)
            cost2 = calculate_cost(usage2["provider"], usage2["model"], usage2.get("input_tokens"), usage2.get("output_tokens"))
            new_usages.append({
                "purpose": "verify",
                "provider": usage2["provider"],
                "model": usage2["model"],
                "input_tokens": usage2.get("input_tokens"),
                "output_tokens": usage2.get("output_tokens"),
                "cost_usd": cost2,
                "latency_ms": usage2.get("latency_ms"),
            })
        except Exception as e:
            logger.error("Optimizer verification call failed: %s", e)
            suggestion.rewritten_prompt = rewritten_prompt
            suggestion.message = f"Verification reply generation failed: {str(e)}"
            suggestion.estimated_token_savings = 0
            suggestion.status = "failed"
            suggestion.similarity_score = None
            suggestion.optimizer_provider = optimizer_client.provider
            suggestion.optimizer_model = optimizer_client.model

            _save_suggestion_and_usages(db, suggestion, existing, new_usages)
            return suggestion

        # Verification: compare embedding of req.reply_text vs new_reply
        embeddings = embedder.embed([req.reply_text, new_reply])
        if len(embeddings) == 2:
            sim = compute_cosine_similarity(embeddings[0], embeddings[1])
            similarity = round(float(sim), 3)
        else:
            similarity = 0.0

        if similarity >= 0.85:
            suggestion.status = "ok"
            suggestion.message = None
        else:
            suggestion.status = "not_verified_safe"
            suggestion.message = f"Semantic similarity between original and new reply is {similarity:.3f} (< 0.85)."

        chars_saved = len(req.prompt_text) - len(rewritten_prompt)
        suggestion.estimated_token_savings = max(0, round(chars_saved / 4))
        suggestion.rewritten_prompt = rewritten_prompt
        suggestion.similarity_score = similarity
        suggestion.optimizer_provider = optimizer_client.provider
        suggestion.optimizer_model = optimizer_client.model

        _save_suggestion_and_usages(db, suggestion, existing, new_usages)
        return suggestion

    return None

def _save_suggestion_and_usages(
    db: Session,
    suggestion: Suggestion,
    existing: Optional[Suggestion],
    new_usages: list,
):
    """
    Saves suggestion and any usage records inside one short transaction.
    Catches IntegrityError on concurrent duplicate flag_id inserts.
    """
    try:
        if not existing:
            db.add(suggestion)
        db.flush()

        for u in new_usages:
            usage_rec = OptimizerUsage(
                suggestion_id=suggestion.id,
                purpose=u["purpose"],
                provider=u["provider"],
                model=u["model"],
                input_tokens=u["input_tokens"],
                output_tokens=u["output_tokens"],
                cost_usd=u["cost_usd"],
                latency_ms=u["latency_ms"],
                created_at=utc_now(),
            )
            db.add(usage_rec)

        db.commit()
        db.refresh(suggestion)
    except IntegrityError:
        db.rollback()
