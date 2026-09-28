import pytest
from unittest.mock import patch, AsyncMock
from app.database import Base, engine, SessionLocal
from app.models import RequestLog
import httpx
import time

def setup_module():
    Base.metadata.create_all(bind=engine)
    
def teardown_module():
    Base.metadata.drop_all(bind=engine)

def test_unknown_provider(client):
    response = client.post("/proxy/unknown-provider", json={"model": "test"})
    assert response.status_code == 404
    
def test_stream_not_supported(client):
    response = client.post("/proxy/groq", json={"stream": True, "model": "test"})
    assert response.status_code == 400
    assert "Streaming is not supported yet" in response.text

@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_mocked_upstream_success(mock_post, client):
    mock_response = httpx.Response(200, json={
        "id": "chatcmpl-123",
        "choices": [{"message": {"role": "assistant", "content": "Mocked response"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    }, request=httpx.Request("POST", "http://test"))
    mock_post.return_value = mock_response

    req_body = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "test"}]
    }

    response = client.post("/proxy/openai", json=req_body)
    assert response.status_code == 200
    
    # Wait for the BackgroundTask to save to DB
    time.sleep(0.1)
    
    db = SessionLocal()
    logs = db.query(RequestLog).all()
    assert len(logs) > 0
    latest = logs[-1]
    assert latest.provider == "openai"
    assert latest.model == "gpt-3.5-turbo"
    assert latest.input_tokens == 10
    assert latest.output_tokens == 20
    assert latest.total_tokens == 30
    assert latest.cost_usd is not None
    assert latest.reply_text == "Mocked response"
    assert latest.prompt_text == "user: test"
    db.close()
