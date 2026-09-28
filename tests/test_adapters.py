import json
from pathlib import Path
from app.provider_config import providers
from app.adapter import resolve_dot_path, extract_prompt_text

def load_fixture(name):
    path = Path(__file__).parent / "fixtures" / f"{name}_response.json"
    with open(path) as f:
        return json.load(f)

def test_openai_adapter():
    data = load_fixture("openai")
    cfg = providers["openai"]
    assert resolve_dot_path(data, cfg.response_paths.reply_text) == "Hello there, how may I assist you today?"
    assert resolve_dot_path(data, cfg.response_paths.input_tokens) == 9
    assert resolve_dot_path(data, cfg.response_paths.output_tokens) == 12
    assert resolve_dot_path(data, cfg.response_paths.total_tokens) == 21

def test_anthropic_adapter():
    data = load_fixture("anthropic")
    cfg = providers["anthropic"]
    assert resolve_dot_path(data, cfg.response_paths.reply_text) == "Hello! How can I help you today?"
    assert resolve_dot_path(data, cfg.response_paths.input_tokens) == 15
    assert resolve_dot_path(data, cfg.response_paths.output_tokens) == 9
    assert resolve_dot_path(data, cfg.response_paths.total_tokens) is None

def test_gemini_adapter():
    data = load_fixture("gemini")
    cfg = providers["gemini"]
    assert resolve_dot_path(data, cfg.response_paths.reply_text) == "Greetings! What can I do for you?"
    assert resolve_dot_path(data, cfg.response_paths.input_tokens) == 10
    assert resolve_dot_path(data, cfg.response_paths.output_tokens) == 8
    assert resolve_dot_path(data, cfg.response_paths.total_tokens) == 18

def test_ollama_adapter():
    data = load_fixture("ollama")
    cfg = providers["ollama"]
    assert resolve_dot_path(data, cfg.response_paths.reply_text) == "Hi there!"
    assert resolve_dot_path(data, cfg.response_paths.input_tokens) == 26
    assert resolve_dot_path(data, cfg.response_paths.output_tokens) == 14
    assert resolve_dot_path(data, cfg.response_paths.total_tokens) is None

def test_groq_adapter():
    data = load_fixture("groq")
    cfg = providers["groq"]
    assert resolve_dot_path(data, cfg.response_paths.reply_text) == "Hi! How can I help?"
    assert resolve_dot_path(data, cfg.response_paths.input_tokens) == 5
    assert resolve_dot_path(data, cfg.response_paths.output_tokens) == 7
    assert resolve_dot_path(data, cfg.response_paths.total_tokens) == 12

def test_extract_openai_messages():
    body = {"messages": [{"role": "user", "content": "hello"}]}
    assert extract_prompt_text("openai_messages", body) == "user: hello"
