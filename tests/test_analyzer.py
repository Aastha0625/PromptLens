import pytest
import json
import hashlib
from datetime import datetime
from typing import List

from app.models import RequestLog, PromptFlag, PromptAnalysis
from app.analyzer import (
    strip_role_prefixes,
    extract_template_key,
    split_sentences,
    find_exact_duplicates,
    find_near_duplicates,
    check_repeated_content,
    analyze_prompt,
)
from app.analysis_service import run_analysis
from app.embedder import Embedder, compute_cosine_similarity

class FakeEmbedder:
    """
    Fake embedder for fast offline testing.
    Produces deterministic embeddings so tests never require internet or large models.
    Identical or marked similar texts get identical vectors; others get orthogonal vectors.
    """
    def __init__(self, similarity_map=None):
        self.similarity_map = similarity_map or {}
        self._call_count = 0

    def is_available(self) -> bool:
        return True

    def embed(self, texts: List[str]) -> List[List[float]]:
        self._call_count += 1
        embeddings = []
        for text in texts:
            # If mapped to a canonical key in similarity_map, use that key
            key = self.similarity_map.get(text, text)
            # Hash key to a 4-dimensional unit vector
            h = hashlib.md5(key.encode("utf-8")).digest()
            val0 = (h[0] / 255.0)
            val1 = (h[1] / 255.0)
            val2 = (h[2] / 255.0)
            val3 = (h[3] / 255.0)
            norm = (val0**2 + val1**2 + val2**2 + val3**2)**0.5 or 1.0
            embeddings.append([val0 / norm, val1 / norm, val2 / norm, val3 / norm])
        return embeddings

# ==================== Pure Heuristics Tests ====================

def test_strip_role_prefixes():
    raw = (
        "system: You are a helpful assistant.\n"
        "User: Please summarize the following article.\n"
        "assistant: Here is the summary.\n"
        "user: Thank you!"
    )
    cleaned = strip_role_prefixes(raw)
    expected = (
        "You are a helpful assistant.\n"
        "Please summarize the following article.\n"
        "Here is the summary.\n"
        "Thank you!"
    )
    assert cleaned == expected

def test_extract_template_key():
    prompt = "user: Summarize the following document for our team meeting tomorrow"
    key = extract_template_key(prompt)
    assert key == "summarize the following document for"

    short_prompt = "system: Hello world"
    assert extract_template_key(short_prompt) == "hello world"

def test_split_sentences():
    text = "First sentence here. Second sentence! Third one? Fourth line\nFifth line"
    sentences = split_sentences(text)
    assert len(sentences) == 5
    assert sentences[0] == "First sentence here"
    assert sentences[1] == "Second sentence"
    assert sentences[2] == "Third one"
    assert sentences[3] == "Fourth line"
    assert sentences[4] == "Fifth line"

def test_exact_duplicates_ignore_short_sentences():
    # Sentences with < 4 words should be ignored
    sentences = [
        "Yes ok.",  # 2 words -> ignored
        "Yes ok.",  # 2 words -> ignored
        "This is a longer valid sentence for testing.", # 8 words
        "This is a longer valid sentence for testing.", # exact duplicate
    ]
    dups, indices = find_exact_duplicates(sentences)
    assert len(dups) == 1
    assert dups[0]["original_index"] == 2
    assert dups[0]["duplicate_index"] == 3
    assert dups[0]["similarity"] == 1.0
    assert 3 in indices
    assert 1 not in indices  # short sentence not flagged

def test_near_duplicates_with_fake_embedder():
    s1 = "Please summarize this document thoroughly."
    s2 = "Kindly summarize this document thoroughly."
    sentences = [s1, s2]

    # Map s1 and s2 to produce identical embeddings (cosine similarity == 1.0)
    fake_embedder = FakeEmbedder(similarity_map={s2: s1})
    dups, ran = find_near_duplicates(sentences, fake_embedder, skip_indices=set())

    assert ran is True
    assert len(dups) == 1
    assert dups[0]["similarity"] >= 0.90
    assert dups[0]["type"] == "semantic"

def test_repeated_content():
    # 1. Blank lines (>= 5 blank lines = 6+ newlines)
    text_blank = "Line one\n\n\n\n\n\nLine two"
    flag = check_repeated_content(text_blank)
    assert flag is not None
    assert flag["flag_type"] == "repeated_content"
    data = json.loads(flag["detail"])
    assert any(f["type"] == "consecutive_blank_lines" for f in data["findings"])

    # 2. Spaces (>= 20 spaces)
    text_spaces = "Hello" + (" " * 25) + "World"
    flag = check_repeated_content(text_spaces)
    assert flag is not None
    data = json.loads(flag["detail"])
    assert any(f["type"] == "consecutive_spaces" for f in data["findings"])

    # 3. Repeated words (>= 4 words)
    text_words = "Please note error error error error in log"
    flag = check_repeated_content(text_words)
    assert flag is not None
    data = json.loads(flag["detail"])
    assert any(f["type"] == "repeated_words" for f in data["findings"])

# ==================== Database & Grouping Tests ====================

def test_verbose_grouping_bounds(db_session):
    """
    Tests the strict grouping boundary requirements:
    - Group of exactly 2 requests: MUST NOT be flagged even with huge ratio.
    - Group of exactly 3 requests: MUST be flagged if ratio >= 3.0x min.
    """
    now = datetime(2024, 1, 1, 10, 0, 0)

    # --- Group A: Exactly 2 requests (template: 'classify the following input text') ---
    req_a1 = RequestLog(
        provider="openai", model="gpt-4o", prompt_text="user: Classify the following input text A",
        input_tokens=10, status_code=200, created_at=now
    )
    req_a2 = RequestLog(
        provider="openai", model="gpt-4o", prompt_text="user: Classify the following input text B with huge padding text " * 10,
        input_tokens=100,  # 10x ratio, but group size is only 2!
        status_code=200, created_at=now
    )

    # --- Group B: Exactly 3 requests (template: 'extract all dates and times') ---
    req_b1 = RequestLog(
        provider="groq", model="llama3", prompt_text="user: Extract all dates and times from A",
        input_tokens=20, status_code=200, created_at=now
    )
    req_b2 = RequestLog(
        provider="groq", model="llama3", prompt_text="user: Extract all dates and times from B",
        input_tokens=22, status_code=200, created_at=now
    )
    req_b3 = RequestLog(
        provider="groq", model="llama3", prompt_text="user: Extract all dates and times from C with verbose text " * 10,
        input_tokens=120,  # 120 / 20 = 6.0x ratio -> high severity, group size is 3!
        status_code=200, created_at=now
    )

    db_session.add_all([req_a1, req_a2, req_b1, req_b2, req_b3])
    db_session.commit()

    fake_embedder = FakeEmbedder()
    res = run_analysis(db_session, embedder=fake_embedder)

    assert res["requests_analyzed"] == 5

    # Check flags for req_a2: MUST NOT have verbose_for_template flag because group size == 2
    flags_a2 = db_session.query(PromptFlag).filter(PromptFlag.request_id == req_a2.id, PromptFlag.flag_type == "verbose_for_template").all()
    assert len(flags_a2) == 0

    # Check flags for req_b3: MUST have verbose_for_template flag with high severity (ratio 6.0 >= 5.0)
    flags_b3 = db_session.query(PromptFlag).filter(PromptFlag.request_id == req_b3.id, PromptFlag.flag_type == "verbose_for_template").all()
    assert len(flags_b3) == 1
    assert flags_b3[0].severity == "high"
    detail = json.loads(flags_b3[0].detail)
    assert detail["group_size"] == 3
    assert detail["min_input_tokens"] == 20
    assert detail["ratio"] == 6.0

def test_idempotent_reanalysis(db_session):
    """
    Verifies that running analysis twice with reanalyze=True replaces flags cleanly
    without duplicating records or leaving stale flags.
    """
    now = datetime(2024, 1, 1, 10, 0, 0)
    req = RequestLog(
        provider="openai",
        model="gpt-4o",
        prompt_text="user: Hello world! This is a repeated sentence. This is a repeated sentence.",
        input_tokens=30,
        status_code=200,
        created_at=now,
    )
    db_session.add(req)
    db_session.commit()

    fake_embedder = FakeEmbedder()

    # First run
    res1 = run_analysis(db_session, embedder=fake_embedder)
    assert res1["requests_analyzed"] == 1
    initial_flags = db_session.query(PromptFlag).filter(PromptFlag.request_id == req.id).all()
    initial_flag_count = len(initial_flags)
    assert initial_flag_count > 0

    # Second run without reanalyze -> should skip
    res2 = run_analysis(db_session, embedder=fake_embedder, reanalyze=False)
    assert res2["requests_analyzed"] == 0

    # Third run with reanalyze -> should re-evaluate and maintain identical flag count
    res3 = run_analysis(db_session, embedder=fake_embedder, reanalyze=True)
    assert res3["requests_analyzed"] == 1
    new_flags = db_session.query(PromptFlag).filter(PromptFlag.request_id == req.id).all()
    assert len(new_flags) == initial_flag_count

@pytest.mark.slow
def test_real_sentence_transformers_embedder():
    """
    Slow test running the real SentenceTransformer 'all-MiniLM-L6-v2' model if installed.
    Verifies semantic cosine similarity >= 0.90 on near-identical text.
    """
    embedder = Embedder.get_instance()
    if not embedder.is_available():
        pytest.skip("sentence-transformers is not installed or model failed to load.")

    texts = [
        "The quick brown fox jumps over the lazy dog.",
        "A fast brown fox leaped over a lazy dog.",
    ]
    embeddings = embedder.embed(texts)
    assert len(embeddings) == 2

    sim = compute_cosine_similarity(embeddings[0], embeddings[1])
    assert sim >= 0.85
