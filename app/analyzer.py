import re
import json
import logging
from typing import List, Dict, Any, Tuple, Optional, Set

from .analyzer_config import (
    ANALYZER_VERSION,
    MIN_WORDS_PER_SENTENCE,
    SIMILARITY_THRESHOLD,
    MAX_SENTENCES_EMBEDDED,
    REDUNDANCY_SEVERITY_HIGH_PCT,
    REDUNDANCY_SEVERITY_MEDIUM_PCT,
    REPEATED_BLANK_LINES,
    REPEATED_SPACES,
    REPEATED_WORDS,
)
from .embedder import Embedder, compute_cosine_similarity

logger = logging.getLogger(__name__)

def strip_role_prefixes(text: str) -> str:
    """
    Strips leading role prefixes (e.g. 'system:', 'user:', 'assistant:')
    from every line so role labels are not counted as prompt text.
    """
    if not text:
        return ""
    lines = text.splitlines()
    cleaned = [re.sub(r'^(system|user|assistant):\s*', '', line, flags=re.IGNORECASE) for line in lines]
    return "\n".join(cleaned)

def extract_template_key(prompt_text: str) -> str:
    """
    Extracts the first 5 words after stripping role prefixes, lowercased.
    Used for grouping similar prompt templates in SQL.
    """
    if not prompt_text:
        return ""
    cleaned = strip_role_prefixes(prompt_text)
    words = cleaned.lower().split()
    return " ".join(words[:5])

def split_sentences(text: str) -> List[str]:
    """
    Splits text into sentences based on punctuation (. ! ?) and newlines.
    Filters out empty or whitespace-only chunks.
    """
    if not text:
        return []
    # Split on periods, exclamation marks, question marks, and newlines
    raw_chunks = re.split(r'[.!?\n]+', text)
    sentences = [chunk.strip() for chunk in raw_chunks if chunk and chunk.strip()]
    return sentences

def count_words(sentence: str) -> int:
    """Counts words in a sentence by splitting on whitespace."""
    return len(sentence.split())

def find_exact_duplicates(sentences: List[str]) -> Tuple[List[Dict[str, Any]], Set[int]]:
    """
    Finds exact duplicates among sentences with at least MIN_WORDS_PER_SENTENCE words.
    Returns:
        - list of duplicate details
        - set of sentence indices that are duplicates (to avoid re-embedding)
    """
    seen_normalized: Dict[str, int] = {}
    duplicates: List[Dict[str, Any]] = []
    duplicate_indices: Set[int] = set()

    for idx, sentence in enumerate(sentences):
        if count_words(sentence) < MIN_WORDS_PER_SENTENCE:
            continue

        # Normalize whitespace and case for exact comparison
        norm = " ".join(sentence.lower().split())
        if norm in seen_normalized:
            original_idx = seen_normalized[norm]
            duplicate_indices.add(idx)
            # Estimated wasted tokens: chars / 4 rounded
            wasted = round(len(sentence) / 4)
            duplicates.append({
                "type": "exact",
                "original_index": original_idx,
                "duplicate_index": idx,
                "snippet_1": sentences[original_idx][:80],
                "snippet_2": sentence[:80],
                "similarity": 1.0,
                "estimated_wasted_tokens": wasted,
            })
        else:
            seen_normalized[norm] = idx

    return duplicates, duplicate_indices

def find_near_duplicates(
    sentences: List[str],
    embedder: Optional[Embedder],
    skip_indices: Set[int],
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Embeds non-duplicate sentences (up to MAX_SENTENCES_EMBEDDED) in ONE batch,
    and flags pairs with cosine similarity >= SIMILARITY_THRESHOLD.
    Returns:
        - list of near-duplicate details
        - boolean indicating whether semantic embedding check ran
    """
    if embedder is None or not embedder.is_available():
        return [], False

    # Filter eligible sentences: min words and not already an exact duplicate
    eligible_items: List[Tuple[int, str]] = []
    for idx, sentence in enumerate(sentences):
        if idx in skip_indices:
            continue
        if count_words(sentence) >= MIN_WORDS_PER_SENTENCE:
            eligible_items.append((idx, sentence))

    # Cap at MAX_SENTENCES_EMBEDDED per prompt to bound processing time and memory
    eligible_items = eligible_items[:MAX_SENTENCES_EMBEDDED]
    if len(eligible_items) < 2:
        return [], True

    texts = [item[1] for item in eligible_items]
    embeddings = embedder.embed(texts)
    if not embeddings or len(embeddings) != len(texts):
        return [], False

    near_duplicates: List[Dict[str, Any]] = []
    n = len(eligible_items)

    for i in range(n):
        for j in range(i + 1, n):
            sim = compute_cosine_similarity(embeddings[i], embeddings[j])
            if sim >= SIMILARITY_THRESHOLD:
                idx_i, text_i = eligible_items[i]
                idx_j, text_j = eligible_items[j]
                wasted = round(len(text_j) / 4)
                near_duplicates.append({
                    "type": "semantic",
                    "original_index": idx_i,
                    "duplicate_index": idx_j,
                    "snippet_1": text_i[:80],
                    "snippet_2": text_j[:80],
                    "similarity": round(float(sim), 3),
                    "estimated_wasted_tokens": wasted,
                })

    return near_duplicates, True

def check_redundant_sentences(
    sentences: List[str],
    total_tokens: int,
    embedder: Optional[Embedder],
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Combines exact and semantic sentence redundancy checks into a single flag if found.
    """
    exact_dups, exact_indices = find_exact_duplicates(sentences)
    near_dups, semantic_ran = find_near_duplicates(sentences, embedder, exact_indices)

    all_dups = exact_dups + near_dups
    if not all_dups:
        return None, semantic_ran

    total_wasted = sum(d["estimated_wasted_tokens"] for d in all_dups)
    effective_tokens = max(total_tokens, 1)
    pct = total_wasted / effective_tokens

    # Determine severity based on wasted tokens ratio
    if pct >= REDUNDANCY_SEVERITY_HIGH_PCT:
        severity = "high"
    elif pct >= REDUNDANCY_SEVERITY_MEDIUM_PCT:
        severity = "medium"
    else:
        severity = "low"

    detail = {
        "duplicates": all_dups,
        "total_estimated_wasted_tokens": total_wasted,
        "prompt_tokens": total_tokens,
        "wasted_percentage": round(pct * 100, 1),
    }

    flag = {
        "flag_type": "redundant_sentences",
        "severity": severity,
        "detail": json.dumps(detail),
        "analyzer_version": ANALYZER_VERSION,
    }
    return flag, semantic_ran

def check_repeated_content(prompt_text: str) -> Optional[Dict[str, Any]]:
    """
    Checks for cosmetic but wasteful repetitions:
    1. >= 5 consecutive blank lines
    2. >= 20 consecutive spaces
    3. >= 4 consecutive repeated words
    """
    if not prompt_text:
        return None

    findings: List[Dict[str, Any]] = []
    total_wasted = 0

    # 1. Check blank lines: 5 blank lines means at least 6 consecutive newlines
    blank_pattern = re.compile(r'(?:[ \t]*\r?\n){6,}')
    for match in blank_pattern.finditer(prompt_text):
        count_newlines = match.group().count('\n')
        # Each extra blank line is approx 1 token wasted
        wasted = max(1, round(len(match.group()) / 4))
        total_wasted += wasted
        findings.append({
            "type": "consecutive_blank_lines",
            "count": count_newlines - 1,
            "estimated_wasted_tokens": wasted,
        })

    # 2. Check 20+ spaces in a row
    space_pattern = re.compile(r'[ ]{20,}')
    for match in space_pattern.finditer(prompt_text):
        wasted = round((len(match.group()) - 1) / 4)
        total_wasted += wasted
        findings.append({
            "type": "consecutive_spaces",
            "count": len(match.group()),
            "estimated_wasted_tokens": wasted,
        })

    # 3. Check 4+ repeated words in a row: e.g. "word word word word"
    word_pattern = re.compile(r'\b([a-zA-Z0-9]+)(?:\s+\1){3,}\b', flags=re.IGNORECASE)
    for match in word_pattern.finditer(prompt_text):
        full_match = match.group()
        first_word = match.group(1)
        # Count occurrences
        occurrences = len(re.findall(re.escape(first_word), full_match, flags=re.IGNORECASE))
        wasted = round((len(full_match) - len(first_word)) / 4)
        total_wasted += wasted
        findings.append({
            "type": "repeated_words",
            "word": first_word,
            "count": occurrences,
            "estimated_wasted_tokens": wasted,
        })

    if not findings:
        return None

    detail = {
        "findings": findings,
        "total_estimated_wasted_tokens": total_wasted,
    }

    return {
        "flag_type": "repeated_content",
        "severity": "low",
        "detail": json.dumps(detail),
        "analyzer_version": ANALYZER_VERSION,
    }

def analyze_prompt(
    prompt_text: str,
    total_tokens: Optional[int] = None,
    embedder: Optional[Embedder] = None,
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Analyzes a single prompt for redundancy and repeated content.
    Returns:
        - list of generated flag dictionaries
        - boolean indicating whether the semantic check was executed
    """
    if not prompt_text:
        return [], False

    # 1. Clean role prefixes
    cleaned_text = strip_role_prefixes(prompt_text)
    effective_tokens = total_tokens if total_tokens and total_tokens > 0 else round(len(cleaned_text) / 4)

    flags: List[Dict[str, Any]] = []

    # 2. Check redundant sentences
    sentences = split_sentences(cleaned_text)
    redundancy_flag, semantic_ran = check_redundant_sentences(sentences, effective_tokens, embedder)
    if redundancy_flag:
        flags.append(redundancy_flag)

    # 3. Check repeated content
    repeated_flag = check_repeated_content(cleaned_text)
    if repeated_flag:
        flags.append(repeated_flag)

    return flags, semantic_ran
