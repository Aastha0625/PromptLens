import copy
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from .analyzer import analyze_prompt
from .config import settings
from .fluff_cleaner import clean_conversational_fluff
from .optimizer_client import OptimizerClient
from .rewriter import apply_rule_based_rewrite

logger = logging.getLogger(__name__)

_CATEGORY_EXPLANATIONS = {
    "greeting": "Removed greeting and conversational preamble.",
    "polite_filler": "Removed polite conversational filler.",
    "pleasantry": "Removed trailing pleasantries.",
}


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, round(len(text) / 4))


def optimize_prompt_text(
    prompt_text: str,
    provider: Optional[str] = "groq",
    model: Optional[str] = "openai/gpt-oss-20b",
    allow_llm_rewrite: bool = True,
    optimizer_client: Optional[OptimizerClient] = None,
) -> Dict[str, Any]:
    """
    Runs multi-tier real-time optimization on a prompt string:
    1. Conversational fluff & politeness stripping
    2. Exact duplicate sentence removal
    3. Repeated whitespace/word formatting cleanup
    4. Optional Tier 2 LLM rewrite if ENABLE_LLM_REWRITE=true
    """
    original = prompt_text or ""
    if not original.strip():
        return {
            "original_prompt": original,
            "optimized_prompt": original,
            "tokens_original": 0,
            "tokens_optimized": 0,
            "tokens_saved": 0,
            "efficiency_score": 100,
            "flaws_detected": [],
            "explanations": [],
        }

    current_text = original
    flaws_detected: List[str] = []
    explanations: List[str] = []

    # 1. Conversational fluff & politeness removal
    fluff_res = clean_conversational_fluff(current_text)
    if fluff_res.modified:
        current_text = fluff_res.cleaned_text
        flaws_detected.append("conversational_fluff")
        for cat in fluff_res.categories_found:
            msg = _CATEGORY_EXPLANATIONS.get(cat)
            if msg and msg not in explanations:
                explanations.append(msg)
        if not explanations:
            explanations.append("Removed conversational fluff and filler.")

    # 2 & 3. Exact duplicate sentence removal and repeated content cleanup
    flags, _ = analyze_prompt(current_text, embedder=None)
    flags_by_type = {f["flag_type"]: f for f in flags}

    if "redundant_sentences" in flags_by_type:
        flag = flags_by_type["redundant_sentences"]
        rewritten, _, _, status = apply_rule_based_rewrite(
            flag_type="redundant_sentences",
            flag_detail_json=flag["detail"],
            original_prompt_text=current_text,
            flag_analyzer_version=flag["analyzer_version"],
        )
        if status == "ok" and rewritten and rewritten.strip():
            current_text = rewritten
            flaws_detected.append("redundant_sentences")
            try:
                dup_count = len(json.loads(flag["detail"]).get("duplicates", []))
            except Exception:
                dup_count = 1
            noun = "sentence" if dup_count == 1 else "sentences"
            explanations.append(f"Removed {dup_count} duplicate {noun}.")

    # Re-check repeated_content after prior cleanups
    post_flags, _ = analyze_prompt(current_text, embedder=None)
    for pf in post_flags:
        if pf["flag_type"] == "repeated_content":
            rewritten, _, _, status = apply_rule_based_rewrite(
                flag_type="repeated_content",
                flag_detail_json=pf["detail"],
                original_prompt_text=current_text,
                flag_analyzer_version=pf["analyzer_version"],
            )
            if status == "ok" and rewritten and rewritten.strip():
                current_text = rewritten
                flaws_detected.append("repeated_content")
                explanations.append("Collapsed excessive whitespace or repeated words.")
            break

    # 4. Optional Tier 2 LLM rewrite when enabled and prompt is non-trivially long
    if allow_llm_rewrite and settings.ENABLE_LLM_REWRITE and len(current_text) >= 120:
        client = optimizer_client or OptimizerClient(
            provider=settings.OPTIMIZER_PROVIDER or provider,
            model=settings.OPTIMIZER_MODEL or model,
        )
        has_credentials = bool(client.api_key and client.api_key != "your_optimizer_key_here")
        if client.provider == "ollama" or has_credentials or optimizer_client is not None:
            try:
                rewritten, _ = client.generate_rewrite(current_text)
                if rewritten and rewritten.strip() and len(rewritten) < len(current_text):
                    current_text = rewritten.strip()
                    flaws_detected.append("verbose_prompt")
                    explanations.append("Shortened verbose prompt using AI optimizer rewrite.")
            except Exception as exc:
                logger.warning("Pre-flight LLM rewrite failed, falling back to heuristic result: %s", exc)

    tokens_original = _estimate_tokens(original)
    tokens_optimized = _estimate_tokens(current_text)

    if current_text == original or tokens_optimized > tokens_original:
        current_text = original
        tokens_optimized = tokens_original
        tokens_saved = 0
        efficiency_score = 100
    else:
        tokens_saved = max(0, tokens_original - tokens_optimized)
        efficiency_score = max(0, min(100, round((tokens_optimized / tokens_original) * 100)))

    return {
        "original_prompt": original,
        "optimized_prompt": current_text,
        "tokens_original": tokens_original,
        "tokens_optimized": tokens_optimized,
        "tokens_saved": tokens_saved,
        "efficiency_score": efficiency_score,
        "flaws_detected": flaws_detected,
        "explanations": explanations,
    }


def optimize_request_body(extractor_name: str, body: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """
    Applies fast heuristic optimization (fluff + duplicate + formatting) to outgoing
    upstream request payloads before dispatch. Returns (optimized_body, total_tokens_saved).
    """
    updated = copy.deepcopy(body)
    total_saved = 0

    def _clean_text(text: str) -> str:
        nonlocal total_saved
        res = optimize_prompt_text(text, allow_llm_rewrite=False)
        total_saved += res["tokens_saved"]
        return res["optimized_prompt"]

    if extractor_name in ("openai_messages", "ollama_chat"):
        for msg in updated.get("messages", []):
            if isinstance(msg, dict) and msg.get("role") != "assistant" and isinstance(msg.get("content"), str):
                msg["content"] = _clean_text(msg["content"])

    elif extractor_name == "anthropic_messages":
        if isinstance(updated.get("system"), str):
            updated["system"] = _clean_text(updated["system"])
        for msg in updated.get("messages", []):
            if not isinstance(msg, dict) or msg.get("role") == "assistant":
                continue
            content = msg.get("content")
            if isinstance(content, str):
                msg["content"] = _clean_text(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                        part["text"] = _clean_text(part["text"])

    elif extractor_name == "gemini_contents":
        for item in updated.get("contents", []):
            if not isinstance(item, dict) or item.get("role") == "model":
                continue
            parts = item.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        part["text"] = _clean_text(part["text"])

    return updated, total_saved
