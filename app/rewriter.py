import re
import json
import logging
from typing import List, Tuple, Optional, Dict, Any, Set
from .analyzer_config import ANALYZER_VERSION

logger = logging.getLogger(__name__)

def get_prompt_sentence_spans(prompt_text: str) -> List[Tuple[int, int, str]]:
    """
    Extracts sentence spans from prompt_text matching the exact sequence of sentences
    analyzed by analyze_prompt(strip_role_prefixes(prompt_text)).
    Returns list of (start_idx, end_idx, sentence_str) relative to prompt_text.
    """
    if not prompt_text:
        return []
    spans = []
    for line_match in re.finditer(r'.*(?:\r?\n|$)', prompt_text):
        full_line = line_match.group()
        if not full_line:
            continue
        line_offset = line_match.start()
        # Find role prefix on this line if present
        role_match = re.match(r'^(system|user|assistant):\s*', full_line, flags=re.IGNORECASE)
        content_start = role_match.end() if role_match else 0
        content = full_line[content_start:]

        for m in re.finditer(r'[^.!?\r\n]+', content):
            raw_chunk = m.group()
            stripped = raw_chunk.strip()
            if stripped:
                lead_ws = len(raw_chunk) - len(raw_chunk.lstrip())
                start_in_prompt = line_offset + content_start + m.start() + lead_ws
                end_in_prompt = start_in_prompt + len(stripped)
                spans.append((start_in_prompt, end_in_prompt, stripped))
    return spans

def split_by_code_blocks(text: str) -> List[Tuple[bool, str]]:
    """
    Splits text into chunks of (is_code_block, content).
    Fenced code blocks start with ``` and end with ```.
    """
    pattern = re.compile(r'(```.*?```)', flags=re.DOTALL)
    parts = []
    last_end = 0
    for match in pattern.finditer(text):
        if match.start() > last_end:
            parts.append((False, text[last_end:match.start()]))
        parts.append((True, match.group(0)))
        last_end = match.end()
    if last_end < len(text):
        parts.append((False, text[last_end:]))
    return parts

def collapse_repeated_content_segment(text: str) -> str:
    """
    Collapses whitespace runs and word repetitions outside code blocks:
    - >= 5 blank lines (6+ newlines) -> single blank line (\n\n)
    - >= 20 spaces -> single space (' ')
    - >= 4 consecutive repeated words -> single word
    """
    # 1. Collapse >= 5 blank lines (6+ newlines with optional spaces) down to \n\n
    text = re.sub(r'(?:[ \t]*\r?\n){6,}', '\n\n', text)

    # 2. Collapse >= 20 spaces down to single space
    text = re.sub(r'[ ]{20,}', ' ', text)

    # 3. Collapse >= 4 consecutive repeated words down to 1
    # e.g. "word word word word" -> "word"
    word_pattern = re.compile(r'\b([a-zA-Z0-9]+)(?:\s+\1){3,}\b', flags=re.IGNORECASE)
    text = word_pattern.sub(r'\1', text)

    return text

def remove_sentence_spans(text: str, spans_to_remove: List[Tuple[int, int]]) -> str:
    """
    Removes sentence spans in reverse order, cleaning up attached punctuation and whitespace.
    """
    if not spans_to_remove:
        return text

    # Sort spans in reverse order of start position so earlier offsets remain valid
    sorted_spans = sorted(spans_to_remove, key=lambda s: s[0], reverse=True)
    chars = list(text)

    for start, end in sorted_spans:
        # Extend end to consume trailing sentence delimiter (. ! ?) and following whitespace if present
        del_end = end
        while del_end < len(chars) and chars[del_end] in ".!? \t":
            del_end += 1
            if del_end < len(chars) and chars[del_end - 1] in ".!?":
                # Stopped after consuming terminator
                break

        # Also consume leading whitespace if sentence was preceded by space
        del_start = start
        if del_start > 0 and chars[del_start - 1] in " \t":
            del_start -= 1

        chars[del_start:del_end] = []

    result = "".join(chars)

    # Clean up any lines that only contain a role prefix or empty spaces
    cleaned_lines = []
    for line in result.splitlines():
        # If line only has "user:" or "assistant:" with nothing after
        if re.match(r'^(system|user|assistant):\s*$', line, flags=re.IGNORECASE):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()

def apply_rule_based_rewrite(
    flag_type: str,
    flag_detail_json: str,
    original_prompt_text: str,
    flag_analyzer_version: int,
) -> Tuple[Optional[str], int, Optional[str], str]:
    """
    Applies deterministic rule-based rewriting based on the flag type and detail.
    Returns:
        (rewritten_prompt, estimated_token_savings, message, status)
    status is 'ok' on successful rewrite, or 'no_change' if nothing was modified.
    """
    # 1. Verify analyzer version
    if flag_analyzer_version != ANALYZER_VERSION:
        return None, 0, f"Flag analyzer version ({flag_analyzer_version}) differs from current ({ANALYZER_VERSION}).", "no_change"

    if not original_prompt_text or not original_prompt_text.strip():
        return None, 0, "Original prompt is empty.", "no_change"

    try:
        detail = json.loads(flag_detail_json) if flag_detail_json else {}
    except Exception as e:
        return None, 0, f"Invalid flag detail JSON: {e}", "no_change"

    rewritten_text = original_prompt_text

    if flag_type == "redundant_sentences":
        duplicates = detail.get("duplicates", [])
        duplicate_indices: Set[int] = set()
        for d in duplicates:
            if "duplicate_index" in d:
                duplicate_indices.add(d["duplicate_index"])

        if not duplicate_indices:
            return None, 0, "No duplicate sentence indices found in flag detail.", "no_change"

        spans = get_prompt_sentence_spans(original_prompt_text)
        spans_to_remove = []
        for idx in duplicate_indices:
            if idx < len(spans):
                start, end, _ = spans[idx]
                spans_to_remove.append((start, end))

        rewritten_text = remove_sentence_spans(original_prompt_text, spans_to_remove)

    elif flag_type == "repeated_content":
        parts = split_by_code_blocks(original_prompt_text)
        collapsed_parts = []
        for is_code, content in parts:
            if is_code:
                # Do not collapse inside fenced code blocks
                collapsed_parts.append(content)
            else:
                collapsed_parts.append(collapse_repeated_content_segment(content))
        rewritten_text = "".join(collapsed_parts)

    else:
        return None, 0, f"Rule-based rewriting is not supported for flag_type '{flag_type}'.", "no_change"

    # If no text was changed
    if rewritten_text == original_prompt_text or not rewritten_text.strip():
        return None, 0, "No redundant content could be safely removed.", "no_change"

    chars_removed = len(original_prompt_text) - len(rewritten_text)
    if chars_removed <= 0:
        return None, 0, "Rewrite was not shorter than original.", "no_change"

    # estimated_token_savings: chars removed / 4 (rounded, clearly an estimate)
    savings = round(chars_removed / 4)
    return rewritten_text, savings, None, "ok"
