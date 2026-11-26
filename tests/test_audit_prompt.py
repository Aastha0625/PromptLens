import time
from unittest.mock import AsyncMock, patch

import httpx

from app.config import settings
from app.fluff_cleaner import clean_conversational_fluff
from app.models import PromptAnalysis, PromptFlag, RequestLog, Suggestion
from app.prompt_optimizer import optimize_prompt_text
from tests.conftest import TestingSessionLocal


class _MockOptimizerClient:
    def __init__(self, rewrite_reply: str):
        self.provider = "mock"
        self.model = "mock-model"
        self.api_key = "test-key"
        self.rewrite_reply = rewrite_reply

    def generate_rewrite(self, original_prompt: str):
        return self.rewrite_reply, {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": 30,
            "output_tokens": 10,
            "latency_ms": 50.0,
        }


# ==================== Fluff Cleaner Tests ====================

def test_fluff_cleaner_strips_greetings_filler_and_pleasantries():
    raw = (
        "Hey ChatGPT, I hope you are having a great day. "
        "Could you please kindly help me with writing a SQL query for top customers? "
        "Thank you so much in advance!"
    )
    res = clean_conversational_fluff(raw)
    assert res.modified is True
    assert res.chars_saved > 0
    assert res.tokens_saved > 0
    assert "Hey ChatGPT" not in res.cleaned_text
    assert "great day" not in res.cleaned_text
    assert "Could you please" not in res.cleaned_text
    assert "Thank you" not in res.cleaned_text
    assert "Writing a SQL query for top customers?" in res.cleaned_text
    assert set(res.categories_found) == {"greeting", "polite_filler", "pleasantry"}


def test_fluff_cleaner_strips_wondering_and_expert_wrappers():
    raw1 = "I was wondering if you could possibly explain Docker volumes. Thanks!"
    res1 = clean_conversational_fluff(raw1)
    assert res1.cleaned_text == "Explain Docker volumes."

    raw2 = "Please act as an expert and review this API design."
    res2 = clean_conversational_fluff(raw2)
    assert res2.cleaned_text == "Review this API design."


def test_fluff_cleaner_preserves_code_blocks_and_technical_hello():
    raw = (
        "Hello AI, please write a Hello world script in Python.\n"
        "```python\n"
        "print('Hey ChatGPT! Thank you so much!')\n"
        "```\n"
        "Thanks!"
    )
    res = clean_conversational_fluff(raw)
    assert res.modified is True
    assert "Write a Hello world script in Python." in res.cleaned_text
    assert "print('Hey ChatGPT! Thank you so much!')" in res.cleaned_text
    assert not res.cleaned_text.endswith("Thanks!")


def test_fluff_cleaner_preserves_role_prefixes_and_pure_filler_guard():
    raw = (
        "user: Good morning! Could you summarize this?\n"
        "user: Thank you so much!"
    )
    res = clean_conversational_fluff(raw)
    assert res.cleaned_text == "user: Summarize this?"

    # Pure filler alone should not collapse to empty string
    only_filler = "Hello! Thank you!"
    res_guard = clean_conversational_fluff(only_filler)
    assert res_guard.cleaned_text == only_filler
    assert res_guard.modified is False


# ==================== Pre-Flight /api/audit-prompt Tests ====================

def test_audit_prompt_endpoint_combined_cleanup(client):
    prompt = (
        "Hey ChatGPT, could you please help me with summarizing the sales report? "
        "Please include the top three regional trends in your summary. "
        "Please include the top three regional trends in your summary. "
        "Note note note note the Q4 spike. "
        "Thanks!"
    )
    resp = client.post(
        "/api/audit-prompt",
        json={"prompt_text": prompt, "provider": "groq", "model": "openai/gpt-oss-20b"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["original_prompt"] == prompt
    assert len(data["optimized_prompt"]) < len(prompt)
    assert data["tokens_original"] > data["tokens_optimized"]
    assert data["tokens_saved"] == data["tokens_original"] - data["tokens_optimized"]
    assert 0 < data["efficiency_score"] < 100
    assert "conversational_fluff" in data["flaws_detected"]
    assert "redundant_sentences" in data["flaws_detected"]
    assert "repeated_content" in data["flaws_detected"]
    assert len(data["explanations"]) >= 3
    assert data["optimized_prompt"].count("top three regional trends") == 1
    assert "Note the Q4 spike." in data["optimized_prompt"]


def test_audit_prompt_endpoint_clean_prompt_returns_100_efficiency(client):
    clean = "Summarize the attached Q4 earnings transcript in 5 bullet points."
    resp = client.post("/api/audit-prompt", json={"prompt_text": clean})
    assert resp.status_code == 200
    data = resp.json()
    assert data["optimized_prompt"] == clean
    assert data["tokens_saved"] == 0
    assert data["efficiency_score"] == 100
    assert data["flaws_detected"] == []
    assert data["explanations"] == []


def test_optimize_prompt_text_optional_tier2_llm_rewrite():
    long_prompt = (
        "Summarize the comprehensive quarterly financial performance report for all departments "
        "including engineering, marketing, sales, operations, and customer support across North America."
    )
    mock_client = _MockOptimizerClient("Summarize Q4 financial performance across all departments.")
    orig_flag = settings.ENABLE_LLM_REWRITE
    settings.ENABLE_LLM_REWRITE = True
    try:
        res = optimize_prompt_text(long_prompt, optimizer_client=mock_client)
        assert res["optimized_prompt"] == "Summarize Q4 financial performance across all departments."
        assert "verbose_prompt" in res["flaws_detected"]
        assert res["tokens_saved"] > 0
    finally:
        settings.ENABLE_LLM_REWRITE = orig_flag


# ==================== Proxy Auto-Audit & Live Auto-Optimize Tests ====================

@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_proxy_auto_audit_on_ingest(mock_post, client, db_session, monkeypatch):
    monkeypatch.setattr("app.proxy.SessionLocal", TestingSessionLocal)
    mock_post.return_value = httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": "Done"}}],
            "usage": {"prompt_tokens": 45, "completion_tokens": 5, "total_tokens": 50},
        },
        request=httpx.Request("POST", "http://test"),
    )

    body = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {
                "role": "user",
                "content": (
                    "Explain how indexing works in PostgreSQL databases. "
                    "Explain how indexing works in PostgreSQL databases. "
                    "Use clear clear clear clear examples."
                ),
            }
        ],
    }
    resp = client.post("/proxy/openai", json=body)
    assert resp.status_code == 200
    time.sleep(0.1)

    req_log = db_session.query(RequestLog).order_by(RequestLog.id.desc()).first()
    assert req_log is not None

    analysis = db_session.query(PromptAnalysis).filter(PromptAnalysis.request_id == req_log.id).first()
    assert analysis is not None
    assert analysis.flag_count >= 1

    flags = db_session.query(PromptFlag).filter(PromptFlag.request_id == req_log.id).all()
    flag_types = {f.flag_type for f in flags}
    assert "redundant_sentences" in flag_types
    assert "repeated_content" in flag_types

    suggestions = db_session.query(Suggestion).filter(Suggestion.request_id == req_log.id).all()
    assert len(suggestions) >= 1
    assert all(s.status == "ok" and s.method == "rule_based" for s in suggestions)


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_proxy_live_auto_optimize_header_and_query(mock_post, client, db_session, monkeypatch):
    monkeypatch.setattr("app.proxy.SessionLocal", TestingSessionLocal)
    mock_post.return_value = httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": "Summary here"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
        },
        request=httpx.Request("POST", "http://test"),
    )

    noisy_content = (
        "Hey ChatGPT, could you please help me with summarizing this release note? "
        "Please highlight breaking changes in the API. "
        "Please highlight breaking changes in the API. "
        "Thank you so much in advance!"
    )
    body = {"model": "openai/gpt-oss-20b", "messages": [{"role": "user", "content": noisy_content}]}

    # 1. Via X-PromptLens-Optimize header
    resp = client.post("/proxy/groq", json=body, headers={"X-PromptLens-Optimize": "true"})
    assert resp.status_code == 200
    assert resp.headers.get("x-promptlens-optimized") == "true"
    assert int(resp.headers.get("x-promptlens-tokens-saved", "0")) > 0

    sent_json = mock_post.call_args.kwargs["json"]
    sent_prompt = sent_json["messages"][0]["content"]
    assert "Hey ChatGPT" not in sent_prompt
    assert "Thank you" not in sent_prompt
    assert sent_prompt.count("highlight breaking changes") == 1

    # 2. Via ?optimize=true query parameter
    resp2 = client.post("/proxy/groq?optimize=true", json=body)
    assert resp2.status_code == 200
    assert resp2.headers.get("x-promptlens-optimized") == "true"
