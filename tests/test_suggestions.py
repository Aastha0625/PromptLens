import pytest
import json
from datetime import datetime

from app.models import RequestLog, PromptFlag, Suggestion, OptimizerUsage
from app.analyzer_config import ANALYZER_VERSION
from app.rewriter import (
    apply_rule_based_rewrite,
    collapse_repeated_content_segment,
    split_by_code_blocks,
)
from app.optimizer_client import clean_llm_rewrite_output
from app.suggestion_service import get_or_create_suggestion
from app.config import settings

class FakeOptimizerClient:
    """Fake client to test Tier 2 without real network calls."""
    def __init__(self, rewrite_reply="Short prompt", verify_reply="Verified reply", fail_on_rewrite=False, fail_on_verify=False, api_key="test-key"):
        self.provider = "mock"
        self.model = "mock-model"
        self.api_key = api_key
        self.rewrite_reply = rewrite_reply
        self.verify_reply = verify_reply
        self.fail_on_rewrite = fail_on_rewrite
        self.fail_on_verify = fail_on_verify
        self.calls = []

    def generate_rewrite(self, original_prompt: str):
        self.calls.append(("rewrite", original_prompt))
        if self.fail_on_rewrite:
            raise RuntimeError("Upstream rewrite failed")
        usage = {"provider": self.provider, "model": self.model, "input_tokens": 20, "output_tokens": 10, "latency_ms": 150.0}
        return self.rewrite_reply, usage

    def generate_reply(self, prompt: str):
        self.calls.append(("verify", prompt))
        if self.fail_on_verify:
            raise RuntimeError("Upstream verify failed")
        usage = {"provider": self.provider, "model": self.model, "input_tokens": 15, "output_tokens": 12, "latency_ms": 110.0}
        return self.verify_reply, usage

class FakeEmbedder:
    """Deterministic fake embedder for verification testing."""
    def __init__(self, similarity=0.90, available=True):
        self._similarity = similarity
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def embed(self, texts):
        if not self._available:
            return []
        if len(texts) == 2:
            return [[1.0, 0.0], [self._similarity, (1.0 - self._similarity**2)**0.5]]
        return [[1.0, 0.0] for _ in texts]

# ==================== Rule-Based Rewriter Tests ====================

def test_rule_based_exact_duplicate_removal():
    prompt = (
        "user: This is sentence number one.\n"
        "This is sentence number two which is long enough.\n"
        "This is sentence number two which is long enough."
    )
    detail = json.dumps({
        "duplicates": [
            {"duplicate_index": 2, "original_index": 1, "snippet_1": "This is sentence number two", "snippet_2": "This is sentence number two"}
        ]
    })
    rewritten, savings, msg, status = apply_rule_based_rewrite("redundant_sentences", detail, prompt, ANALYZER_VERSION)

    assert status == "ok"
    assert "sentence number two which is long enough" in rewritten
    # Count occurrences: should now appear exactly once
    assert rewritten.count("sentence number two which is long enough") == 1
    assert savings > 0
    assert msg is None

def test_rule_based_repeated_content_protects_code_blocks():
    # Whitespace and repeated words inside code blocks must NOT be collapsed (Change 9)
    prompt = (
        "Here is text with word word word word error.\n"
        "```python\n"
        "# Code block\n"
        "x = 'word word word word'\n"
        "\n\n\n\n\n\n"
        "print('preserved')\n"
        "```\n"
        "End of prompt."
    )
    detail = json.dumps({"findings": [{"type": "repeated_words"}]})
    rewritten, savings, msg, status = apply_rule_based_rewrite("repeated_content", detail, prompt, ANALYZER_VERSION)

    assert status == "ok"
    # Outside code block: repeated words collapsed
    assert "text with word error." in rewritten
    # Inside code block: repeated words and blank lines preserved
    assert "x = 'word word word word'" in rewritten
    assert "\n\n\n\n\n\n" in rewritten

def test_rule_based_version_mismatch():
    # Analyzer version mismatch must result in status 'no_change' and 0 savings (Change 3)
    prompt = "user: Sentence one. Sentence one."
    detail = json.dumps({"duplicates": [{"duplicate_index": 1}]})
    rewritten, savings, msg, status = apply_rule_based_rewrite("redundant_sentences", detail, prompt, flag_analyzer_version=999)

    assert status == "no_change"
    assert savings == 0
    assert rewritten is None
    assert "differs from current" in msg

# ==================== Change 8: LLM Rewrite Guard Rails Tests ====================

def test_llm_rewrite_guard_rails():
    # 1. Strip markdown fences
    fenced = "```markdown\nThis is the clean prompt.\n```"
    assert clean_llm_rewrite_output(fenced) == "This is the clean prompt."

    # 2. Strip conversational preambles
    preamble = "Here is the rewritten prompt:\nSummarize this text."
    assert clean_llm_rewrite_output(preamble) == "Summarize this text."

    # 3. Strip surrounding quotation marks
    quoted = '"Extract all tables from PDF."'
    assert clean_llm_rewrite_output(quoted) == "Extract all tables from PDF."

def test_llm_rewrite_not_shorter_guard_rail(db_session):
    # If the rewritten prompt is not shorter than original, status is 'no_change' (Change 8)
    req = RequestLog(
        provider="groq", model="llama3", prompt_text="Short prompt",
        reply_text="Baseline reply", input_tokens=10, output_tokens=10,
        status_code=200, created_at=datetime.utcnow()
    )
    db_session.add(req)
    db_session.commit()

    flag = PromptFlag(
        request_id=req.id, flag_type="verbose_for_template", severity="medium",
        detail="{}", created_at=datetime.utcnow(), analyzer_version=ANALYZER_VERSION
    )
    db_session.add(flag)
    db_session.commit()

    # Rewrite is longer than original ("This is a much longer rewrite...")
    fake_client = FakeOptimizerClient(rewrite_reply="This is a much longer rewrite than original prompt.")
    fake_embedder = FakeEmbedder(similarity=0.95)

    original_enable = settings.ENABLE_LLM_REWRITE
    settings.ENABLE_LLM_REWRITE = True
    try:
        sug = get_or_create_suggestion(db_session, flag.id, optimizer_client=fake_client, embedder=fake_embedder)
        assert sug.status == "no_change"
        assert sug.estimated_token_savings == 0
        assert "not shorter" in sug.message
    finally:
        settings.ENABLE_LLM_REWRITE = original_enable

# ==================== Change 2: Preflight Checks Tests ====================

def test_preflight_checks_zero_calls(db_session):
    # Preflight failure must make ZERO optimizer calls (Change 2)
    req = RequestLog(
        provider="groq", model="llama3", prompt_text="Long verbose prompt " * 10,
        reply_text="", # Empty baseline reply!
        input_tokens=100, output_tokens=10, status_code=200, created_at=datetime.utcnow()
    )
    db_session.add(req)
    db_session.commit()

    flag = PromptFlag(
        request_id=req.id, flag_type="verbose_for_template", severity="high",
        detail="{}", created_at=datetime.utcnow(), analyzer_version=ANALYZER_VERSION
    )
    db_session.add(flag)
    db_session.commit()

    fake_client = FakeOptimizerClient()
    fake_embedder = FakeEmbedder()

    original_enable = settings.ENABLE_LLM_REWRITE
    settings.ENABLE_LLM_REWRITE = True
    try:
        # 1. Missing baseline reply_text
        sug = get_or_create_suggestion(db_session, flag.id, optimizer_client=fake_client, embedder=fake_embedder)
        assert sug.status == "not_verified_safe"
        assert "no baseline reply_text" in sug.message
        assert len(fake_client.calls) == 0  # Zero calls!

        # 2. Embedder unavailable
        req.reply_text = "Valid baseline reply"
        db_session.commit()
        unavail_embedder = FakeEmbedder(available=False)
        sug2 = get_or_create_suggestion(db_session, flag.id, regenerate=True, optimizer_client=fake_client, embedder=unavail_embedder)
        assert sug2.status == "failed"
        assert "embedder is unavailable" in sug2.message
        assert len(fake_client.calls) == 0  # Zero calls!

        # 3. Missing API key
        no_key_client = FakeOptimizerClient(api_key="")
        sug3 = get_or_create_suggestion(db_session, flag.id, regenerate=True, optimizer_client=no_key_client, embedder=fake_embedder)
        assert sug3.status == "failed"
        assert "OPTIMIZER_API_KEY is not configured" in sug3.message
        assert len(no_key_client.calls) == 0  # Zero calls!
    finally:
        settings.ENABLE_LLM_REWRITE = original_enable

# ==================== Change 1 & 4: Idempotency & Nullable Message Tests ====================

def test_idempotency_and_retry_behavior(db_session):
    # Idempotency applies to 'ok' and 'not_verified_safe'. 'disabled' or 'failed' retries in place (Change 1 & 4)
    req = RequestLog(
        provider="groq", model="llama3", prompt_text="Long verbose prompt " * 10,
        reply_text="Baseline reply", input_tokens=100, output_tokens=10,
        status_code=200, created_at=datetime.utcnow()
    )
    db_session.add(req)
    db_session.commit()

    flag = PromptFlag(
        request_id=req.id, flag_type="verbose_for_template", severity="high",
        detail="{}", created_at=datetime.utcnow(), analyzer_version=ANALYZER_VERSION
    )
    db_session.add(flag)
    db_session.commit()

    fake_client = FakeOptimizerClient(rewrite_reply="Short rewrite.")
    fake_embedder = FakeEmbedder(similarity=0.92)

    original_enable = settings.ENABLE_LLM_REWRITE

    # 1. First run with ENABLE_LLM_REWRITE = False -> status "disabled", message set, rewritten_prompt is None
    settings.ENABLE_LLM_REWRITE = False
    sug_disabled = get_or_create_suggestion(db_session, flag.id, optimizer_client=fake_client, embedder=fake_embedder)
    assert sug_disabled.status == "disabled"
    assert sug_disabled.rewritten_prompt is None  # Change 4: nullable, never stores message in rewritten_prompt
    assert "LLM rewriting is disabled" in sug_disabled.message

    # 2. Second run with regenerate=False but ENABLE_LLM_REWRITE = True -> Retries because status was 'disabled' (Change 1)
    settings.ENABLE_LLM_REWRITE = True
    try:
        sug_retried = get_or_create_suggestion(db_session, flag.id, regenerate=False, optimizer_client=fake_client, embedder=fake_embedder)
        assert sug_retried.id == sug_disabled.id  # Same row updated in place!
        assert sug_retried.status == "ok"
        assert sug_retried.rewritten_prompt == "Short rewrite."
        assert sug_retried.message is None

        # 3. Third run with regenerate=False -> Status is now 'ok', so it does NOT re-execute optimizer
        call_count_before = len(fake_client.calls)
        sug_cached = get_or_create_suggestion(db_session, flag.id, regenerate=False, optimizer_client=fake_client, embedder=fake_embedder)
        assert len(fake_client.calls) == call_count_before  # No new calls made!
        assert sug_cached.status == "ok"
    finally:
        settings.ENABLE_LLM_REWRITE = original_enable

# ==================== Change 6: Usage Persistence on Failure & Regenerate Tests ====================

def test_usage_persistence_even_if_later_step_fails(db_session):
    # Call 1 succeeds, Call 2 fails -> Call 1 usage row must still be written (Change 6)
    req = RequestLog(
        provider="groq", model="llama3", prompt_text="Long verbose prompt " * 10,
        reply_text="Baseline reply", input_tokens=100, output_tokens=10,
        status_code=200, created_at=datetime.utcnow()
    )
    db_session.add(req)
    db_session.commit()

    flag = PromptFlag(
        request_id=req.id, flag_type="verbose_for_template", severity="high",
        detail="{}", created_at=datetime.utcnow(), analyzer_version=ANALYZER_VERSION
    )
    db_session.add(flag)
    db_session.commit()

    # Fail on verification call (Call 2)
    fake_client = FakeOptimizerClient(rewrite_reply="Short rewrite.", fail_on_verify=True)
    fake_embedder = FakeEmbedder()

    original_enable = settings.ENABLE_LLM_REWRITE
    settings.ENABLE_LLM_REWRITE = True
    try:
        sug = get_or_create_suggestion(db_session, flag.id, optimizer_client=fake_client, embedder=fake_embedder)
        assert sug.status == "failed"
        assert "Verification reply generation failed" in sug.message

        # Verify that Call 1 (rewrite) usage was still recorded!
        usages = db_session.query(OptimizerUsage).filter(OptimizerUsage.suggestion_id == sug.id).all()
        assert len(usages) == 1
        assert usages[0].purpose == "rewrite"

        # Now regenerate=True with successful client -> keeps old usage and adds 2 new usages (3 total)
        success_client = FakeOptimizerClient(rewrite_reply="Short rewrite.")
        sug_regen = get_or_create_suggestion(db_session, flag.id, regenerate=True, optimizer_client=success_client, embedder=fake_embedder)
        assert sug_regen.id == sug.id
        assert sug_regen.status == "ok"

        all_usages = db_session.query(OptimizerUsage).filter(OptimizerUsage.suggestion_id == sug.id).all()
        assert len(all_usages) == 3  # 1 old + 2 new
    finally:
        settings.ENABLE_LLM_REWRITE = original_enable

# ==================== Change 5: API Endpoints & Summary Savings Tests ====================

def test_api_suggestions_and_summary(client, db_session):
    # Add a prompt flag and generate suggestion via API
    dt = datetime(2024, 1, 1, 12, 0, 0)
    req = RequestLog(
        provider="groq", model="llama3", input_tokens=50, output_tokens=10,
        status_code=200, created_at=dt,
        prompt_text="user: First sentence here. Duplicate sentence here. Duplicate sentence here."
    )
    db_session.add(req)
    db_session.commit()

    flag = PromptFlag(
        request_id=req.id, flag_type="redundant_sentences", severity="medium",
        detail=json.dumps({"duplicates": [{"duplicate_index": 2, "original_index": 1}]}),
        created_at=dt, analyzer_version=ANALYZER_VERSION
    )
    db_session.add(flag)
    db_session.commit()

    # 1. POST /api/suggest/{flag_id}
    r = client.post(f"/api/suggest/{flag.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["method"] == "rule_based"
    assert data["estimated_token_savings"] > 0
    assert data["rewritten_prompt"] is not None

    # 2. GET /api/suggestions (pagination and filter)
    r_list = client.get("/api/suggestions?page=1&page_size=10&method=rule_based&status=ok")
    assert r_list.status_code == 200
    list_data = r_list.json()
    assert list_data["total"] >= 1
    assert len(list_data["items"]) >= 1

    # 3. GET /api/suggestions/summary (Change 5: separate savings breakdown)
    r_sum = client.get("/api/suggestions/summary")
    assert r_sum.status_code == 200
    sum_data = r_sum.json()
    assert sum_data["total_suggestions"] >= 1
    assert sum_data["rule_based_savings"] > 0
    assert sum_data["total_estimated_token_savings"] == sum_data["rule_based_savings"] + sum_data["verified_llm_savings"]

    # 4. Error validation: 404 on unknown flag
    r_404 = client.post("/api/suggest/9999")
    assert r_404.status_code == 404

    # 5. Error validation: 422 on invalid method
    r_422 = client.get("/api/suggestions?method=invalid_method")
    assert r_422.status_code == 422

    # 6. Phase 6: flag_id filter and 422 on non-integer
    r_flag = client.get(f"/api/suggestions?flag_id={flag.id}")
    assert r_flag.status_code == 200
    flag_res = r_flag.json()
    assert flag_res["total"] == 1
    assert flag_res["items"][0]["flag_id"] == flag.id

    r_flag_invalid = client.get("/api/suggestions?flag_id=invalid_id")
    assert r_flag_invalid.status_code == 422
