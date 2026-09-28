from typing import Any, Dict, Optional, Tuple
import os

def resolve_dot_path(data: Dict[str, Any], path: Optional[str]) -> Any:
    if not path or not isinstance(data, dict):
        return None
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list) and key.isdigit() and int(key) < len(current):
            current = current[int(key)]
        else:
            return None
    return current

def extract_openai_messages(body: Dict[str, Any]) -> str:
    messages = body.get("messages", [])
    return "\n".join([f"{m.get('role', '')}: {m.get('content', '')}" for m in messages])

def extract_anthropic_messages(body: Dict[str, Any]) -> str:
    messages = body.get("messages", [])
    lines = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if isinstance(content, list):
            text = " ".join([c.get("text", "") for c in content if c.get("type") == "text"])
            lines.append(f"{role}: {text}")
        else:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)

def extract_gemini_contents(body: Dict[str, Any]) -> str:
    contents = body.get("contents", [])
    lines = []
    for c in contents:
        role = c.get("role", "user")
        parts = c.get("parts", [])
        text = " ".join([p.get("text", "") for p in parts if "text" in p])
        lines.append(f"{role}: {text}")
    return "\n".join(lines)

def extract_ollama_chat(body: Dict[str, Any]) -> str:
    messages = body.get("messages", [])
    return "\n".join([f"{m.get('role', '')}: {m.get('content', '')}" for m in messages])

EXTRACTORS = {
    "openai_messages": extract_openai_messages,
    "anthropic_messages": extract_anthropic_messages,
    "gemini_contents": extract_gemini_contents,
    "ollama_chat": extract_ollama_chat,
}

def extract_prompt_text(extractor_name: str, request_body: Dict[str, Any]) -> str:
    extractor = EXTRACTORS.get(extractor_name)
    if not extractor:
        return ""
    return extractor(request_body)

def get_auth_headers_or_params(provider_config) -> Tuple[Dict[str, str], Dict[str, str]]:
    headers = {}
    params = {}
    api_key = os.environ.get(provider_config.env_var) if provider_config.env_var else None

    if provider_config.auth_style == "bearer" and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif provider_config.auth_style == "x-api-key" and api_key:
        headers["x-api-key"] = api_key
    elif provider_config.auth_style == "query" and api_key:
        params["key"] = api_key

    if provider_config.extra_headers:
        headers.update(provider_config.extra_headers)

    return headers, params
