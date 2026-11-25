import re
from dataclasses import dataclass, field
from typing import List, Tuple

from .rewriter import split_by_code_blocks


@dataclass
class FluffCleanResult:
    """Result of stripping conversational fluff and politeness filler from a prompt."""

    original_text: str
    cleaned_text: str
    original_chars: int
    cleaned_chars: int
    chars_saved: int
    tokens_saved: int
    removed_phrases: List[str] = field(default_factory=list)
    categories_found: List[str] = field(default_factory=list)
    modified: bool = False


_ROLE_PREFIX_RE = re.compile(r"^(system|user|assistant):\s*", flags=re.IGNORECASE)

# Ordered (category, compiled_pattern) rules applied outside fenced code blocks.
# Greeting and pleasantry rules target sentence/line boundaries so technical content
# like "Write a Hello World program" is never touched.
_FLUFF_RULES: List[Tuple[str, re.Pattern]] = [
    (
        "greeting",
        re.compile(
            r"(?:^|(?<=\n)|(?<=[.!?]\s))"
            r"(?:"
            r"(?:hey|hi|hello)\s+(?:chatgpt|claude|gemini|gpt|ai|assistant|bot|there)(?:\s*[!,.:]+|\s+(?=\S))?"
            r"|(?:hey|hi|hello)\s*[!,]+(?:\s+|$)"
            r"|good\s+(?:morning|afternoon|evening)(?:\s*(?:chatgpt|ai|assistant|there))?(?:\s*[!,.:]+|\s+|$)"
            r"|(?:i\s+)?hope\s+you(?:'re|\s+are)\s+(?:doing\s+well|well|having\s+a\s+(?:great|good|wonderful|nice)\s+day)\s*[!.,]*(?:\s+|$)"
            r")",
            flags=re.IGNORECASE,
        ),
    ),
    (
        "polite_filler",
        re.compile(
            r"(?:^|(?<=\n)|(?<=[.!?]\s))"
            r"(?:"
            r"i\s+was\s+wondering\s+if\s+you\s+could\s+(?:(?:possibly|please|kindly)\s+)*(?:help\s+me\s+(?:with|to)\s+)?"
            r"|(?:could|would|can)\s+you\s+(?:(?:please|kindly|possibly)\s+)*(?:mind\s+)?(?:(?:help(?:ing)?|assist(?:ing)?)\s+me\s+(?:with|to)\s+)"
            r"|(?:could|would)\s+you\s+(?:(?:please|kindly|possibly)\s+)*"
            r"|can\s+you\s+(?:(?:please|kindly|possibly)\s+)+"
            r"|please\s+(?:kindly\s+)?act\s+as\s+an\s+expert\s+and\s+"
            r"|(?:please|kindly)\s+(?=[a-zA-Z])"
            r")",
            flags=re.IGNORECASE,
        ),
    ),
    (
        "pleasantry",
        re.compile(
            r"(?:^|(?<=\n)|(?<=[.!?,]\s)|\s+)"
            r"(?:"
            r"thank\s+you(?:\s+(?:so\s+much|very\s+much))?(?:\s+in\s+advance)?\s*[!.]*"
            r"|thanks(?:\s+(?:a\s+lot|so\s+much|very\s+much|in\s+advance))?\s*[!.]*"
            r"|much\s+appreciated\s*[!.]*"
            r"|i\s+really\s+appreciate\s+(?:it|your\s+help)\s*[!.]*"
            r"|have\s+a\s+(?:great|good|nice|wonderful)\s+day\s*[!.]*"
            r")(?=\s*(?:\n|$))",
            flags=re.IGNORECASE,
        ),
    ),
]


def _capitalize_leading_alpha(text: str) -> str:
    """Capitalize the first alphabetic character if stripping a prefix left lowercase."""
    for idx, ch in enumerate(text):
        if ch.isalpha():
            if ch.islower():
                return text[:idx] + ch.upper() + text[idx + 1 :]
            return text
        if not ch.isspace():
            return text
    return text


def _clean_segment_text(segment: str, removed: List[str], categories: List[str]) -> str:
    """Apply fluff removal rules across non-code text while preserving role prefixes."""
    lines = segment.splitlines(keepends=True)
    cleaned_lines: List[str] = []

    for line in lines:
        line_ending = ""
        body = line
        if body.endswith("\r\n"):
            line_ending = "\r\n"
            body = body[:-2]
        elif body.endswith("\n"):
            line_ending = "\n"
            body = body[:-1]

        role_prefix = ""
        content = body
        role_match = _ROLE_PREFIX_RE.match(body)
        if role_match:
            role_prefix = role_match.group(0)
            content = body[role_match.end() :]

        original_content = content
        # Loop until no further leading/trailing fluff rule matches (handles stacked
        # phrases like "Hey ChatGPT, could you please help me with...").
        changed = True
        while changed and content:
            changed = False
            for category, pattern in _FLUFF_RULES:
                match = pattern.search(content)
                if match:
                    matched_text = match.group(0).strip()
                    if matched_text:
                        removed.append(matched_text)
                        if category not in categories:
                            categories.append(category)
                    content = (content[: match.start()] + content[match.end() :]).strip()
                    changed = True

        if content and content != original_content:
            content = _capitalize_leading_alpha(content)

        if role_prefix and not content:
            # Drop lines that had only a role prefix and pure filler (e.g. "user: Thanks!")
            continue
        if not role_prefix and not content and original_content.strip():
            # Entire non-empty line was filler; drop it
            continue

        cleaned_lines.append(f"{role_prefix}{content}{line_ending}")

    return "".join(cleaned_lines).strip()


def clean_conversational_fluff(text: str) -> FluffCleanResult:
    """
    Strip conversational greetings, polite filler, and trailing pleasantries from a prompt
    while preserving fenced code blocks and role prefixes.
    """
    if not text or not text.strip():
        return FluffCleanResult(
            original_text=text or "",
            cleaned_text=text or "",
            original_chars=len(text or ""),
            cleaned_chars=len(text or ""),
            chars_saved=0,
            tokens_saved=0,
        )

    removed_phrases: List[str] = []
    categories: List[str] = []
    parts = split_by_code_blocks(text)
    cleaned_parts: List[str] = []

    for is_code, content in parts:
        if is_code:
            cleaned_parts.append(content)
        else:
            cleaned_parts.append(_clean_segment_text(content, removed_phrases, categories))

    cleaned = "\n".join(p for p in cleaned_parts if p != "").strip() if any(p for p in cleaned_parts) else ""
    # Rejoin preserving spacing when code blocks and text alternate cleanly
    if any(is_code for is_code, _ in parts):
        rebuilt: List[str] = []
        for piece in cleaned_parts:
            if not piece:
                continue
            if rebuilt and not rebuilt[-1].endswith("\n") and not piece.startswith("\n"):
                rebuilt.append("\n")
            rebuilt.append(piece)
        cleaned = "".join(rebuilt).strip()

    # Safety guard: never return an empty prompt if the original had non-whitespace content
    if not cleaned:
        return FluffCleanResult(
            original_text=text,
            cleaned_text=text,
            original_chars=len(text),
            cleaned_chars=len(text),
            chars_saved=0,
            tokens_saved=0,
        )

    chars_saved = max(0, len(text) - len(cleaned))
    tokens_saved = round(chars_saved / 4)
    return FluffCleanResult(
        original_text=text,
        cleaned_text=cleaned,
        original_chars=len(text),
        cleaned_chars=len(cleaned),
        chars_saved=chars_saved,
        tokens_saved=tokens_saved,
        removed_phrases=removed_phrases,
        categories_found=categories,
        modified=(cleaned != text and chars_saved > 0),
    )
