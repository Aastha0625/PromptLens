from datetime import datetime
from app.models import RequestLog

def test_summary_empty(client):
    r = client.get("/api/stats/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["total_requests"] == 0
    assert data["total_cost_usd"] == 0.0

def test_date_validation(client):
    r = client.get("/api/stats/summary?from=2024-01-02T00:00:00Z&to=2024-01-01T00:00:00Z")
    assert r.status_code == 422

def test_timeline_gap_filling(client, db_session):
    # Insert 1 request
    dt = datetime(2024, 1, 1, 12, 0, 0)
    db_session.add(RequestLog(
        provider="ollama", model="llama3", input_tokens=10, output_tokens=10, 
        total_tokens=20, cost_usd=0, latency_ms=100, status_code=200, created_at=dt
    ))
    db_session.commit()
    
    r = client.get("/api/stats/timeline?from=2024-01-01T10:00:00&to=2024-01-01T14:00:00&bucket=hour")
    assert r.status_code == 200
    data = r.json()
    # 10, 11, 12, 13, 14 = 5 buckets
    assert len(data) == 5
    assert data[0]["bucket_start"] == "2024-01-01 10:00:00"
    assert data[0]["requests"] == 0
    assert data[2]["bucket_start"] == "2024-01-01 12:00:00"
    assert data[2]["requests"] == 1

def test_summary_math(client, db_session):
    dt = datetime(2024, 1, 1, 12, 0, 0)
    
    # Successful priced
    db_session.add(RequestLog(
        provider="groq", model="llama3", input_tokens=10, output_tokens=10, 
        total_tokens=20, cost_usd=0.5, latency_ms=100, status_code=200, created_at=dt
    ))
    
    # Successful unpriced
    db_session.add(RequestLog(
        provider="groq", model="unknown", input_tokens=10, output_tokens=10, 
        total_tokens=20, cost_usd=None, latency_ms=300, status_code=200, created_at=dt
    ))
    
    # Failed
    db_session.add(RequestLog(
        provider="openai", model="gpt-4o", input_tokens=10, output_tokens=0, 
        total_tokens=10, cost_usd=0.1, latency_ms=500, status_code=500, created_at=dt
    ))
    db_session.commit()
    
    r = client.get("/api/stats/summary")
    data = r.json()
    
    assert data["total_requests"] == 3
    assert data["successful_requests"] == 2
    assert data["failed_requests"] == 1
    assert data["total_tokens"] == 50
    assert data["total_cost_usd"] == 0.6  # 0.5 + 0.1, None ignored
    assert data["unpriced_requests"] == 1
    assert data["avg_latency_ms"] == 200.0  # Only 2xx average: (100+300)/2
    
def test_requests_list(client, db_session):
    dt = datetime(2024, 1, 1, 12, 0, 0)
    db_session.add(RequestLog(
        provider="groq", model="llama3", input_tokens=10, output_tokens=10, 
        total_tokens=20, cost_usd=0.5, latency_ms=100, status_code=200, created_at=dt,
        prompt_text="A" * 500
    ))
    db_session.commit()
    
    r = client.get("/api/requests?provider=groq")
    data = r.json()
    assert data["total"] == 1
    assert len(data["items"][0]["prompt_preview"]) == 200
    assert "prompt_text" not in data["items"][0]
    
def test_404(client):
    r = client.get("/api/requests/999")
    assert r.status_code == 404

def test_api_analyze_and_flags(client, db_session):
    dt = datetime(2024, 1, 1, 12, 0, 0)
    # Add a request with repeated words and redundant sentences
    db_session.add(RequestLog(
        provider="groq", model="llama3", input_tokens=40, output_tokens=10,
        total_tokens=50, cost_usd=0.0, latency_ms=100, status_code=200, created_at=dt,
        prompt_text="user: Hello world! This is a test sentence for duplicate check. This is a test sentence for duplicate check. Test test test test."
    ))
    db_session.commit()

    # Trigger analyze
    r = client.post("/api/analyze?reanalyze=true")
    assert r.status_code == 200
    res = r.json()
    assert res["requests_analyzed"] == 1
    assert res["requests_flagged"] == 1
    assert res["flags_created"] >= 1

    # Get flags
    r_flags = client.get("/api/flags")
    assert r_flags.status_code == 200
    flags_data = r_flags.json()
    assert flags_data["total"] >= 1
    assert len(flags_data["items"]) >= 1
    item = flags_data["items"][0]
    assert item["provider"] == "groq"
    assert item["model"] == "llama3"
    assert "prompt_preview" in item

    # Get flags summary
    r_summary = client.get("/api/flags/summary")
    assert r_summary.status_code == 200
    sum_data = r_summary.json()
    assert sum_data["analyzed_requests"] == 1
    assert sum_data["flagged_requests"] == 1
    assert sum_data["total_flags"] >= 1
    assert sum_data["total_estimated_wasted_tokens"] > 0

