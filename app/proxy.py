import logging
import time
import httpx
from fastapi import Request, BackgroundTasks, Response
from fastapi.responses import JSONResponse

from .provider_config import providers
from .adapter import extract_prompt_text, get_auth_headers_or_params, resolve_dot_path
from .analysis_service import analyze_single_request
from .cost import calculate_cost
from .database import SessionLocal
from .models import RequestLog
from .prompt_optimizer import optimize_request_body

logger = logging.getLogger(__name__)


def _is_truthy_flag(value: str | None) -> bool:
    return (value or "").strip().lower() in ("true", "1", "yes")


def save_log_to_db(log_data: dict):
    db = SessionLocal()
    try:
        db_log = RequestLog(**log_data)
        db.add(db_log)
        db.commit()
        db.refresh(db_log)

        if db_log.status_code is not None and 200 <= db_log.status_code < 300 and db_log.prompt_text:
            try:
                analyze_single_request(db, db_log, embedder=None, auto_suggest=True)
            except Exception as exc:
                logger.warning("Auto-audit failed for request %s: %s", db_log.id, exc)
                db.rollback()
    finally:
        db.close()


def filter_response_headers(headers: httpx.Headers) -> dict:
    filtered = {}
    for k, v in headers.items():
        if k.lower() not in ["content-encoding", "content-length", "transfer-encoding", "connection"]:
            filtered[k] = v
    return filtered


async def handle_proxy_request(
    provider_name: str,
    request: Request,
    body: dict | None,
    background_tasks: BackgroundTasks,
    http_client: httpx.AsyncClient,
):
    provider_config = providers[provider_name]

    if body is None:
        log_data = {
            "provider": provider_name,
            "status_code": 400,
            "error": "Invalid JSON body",
            "latency_ms": 0,
        }
        background_tasks.add_task(save_log_to_db, log_data)
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    if body.get("stream") is True:
        return JSONResponse(status_code=400, content={"error": "Streaming is not supported yet"})

    should_optimize = _is_truthy_flag(request.headers.get("x-promptlens-optimize")) or _is_truthy_flag(
        request.query_params.get("optimize")
    )
    if should_optimize:
        upstream_body, optimized_tokens_saved = optimize_request_body(provider_config.request_extractor, body)
    else:
        upstream_body, optimized_tokens_saved = body, 0

    model = upstream_body.get("model", provider_config.default_model)
    prompt_text = extract_prompt_text(provider_config.request_extractor, upstream_body)

    url = f"{provider_config.base_url}{provider_config.chat_path}"
    if "{model}" in url and model:
        url = url.replace("{model}", model)

    headers, params = get_auth_headers_or_params(provider_config)

    for k, v in request.headers.items():
        if k.lower() not in ["host", "content-length", "authorization", "x-promptlens-optimize"]:
            headers[k] = v

    # Prioritize the client application's API key if sent in request headers (e.g. from FinAI)
    client_auth = request.headers.get("authorization")
    if client_auth:
        headers["Authorization"] = client_auth
    elif "x-api-key" in request.headers:
        headers["x-api-key"] = request.headers["x-api-key"]

    start_time = time.time()
    try:
        upstream_response = await http_client.post(
            url,
            json=upstream_body,
            headers=headers,
            params=params,
        )
        latency_ms = (time.time() - start_time) * 1000
        status_code = upstream_response.status_code

        try:
            response_json = upstream_response.json()
        except Exception:
            response_json = None

        if status_code >= 400 or not response_json:
            error_msg = upstream_response.text if upstream_response.text else "Unknown upstream error"
            log_data = {
                "provider": provider_name,
                "model": model,
                "prompt_text": prompt_text,
                "status_code": status_code,
                "error": error_msg,
                "latency_ms": latency_ms,
            }
            background_tasks.add_task(save_log_to_db, log_data)
            return Response(
                content=upstream_response.content,
                status_code=status_code,
                headers=filter_response_headers(upstream_response.headers),
            )

        reply_text = resolve_dot_path(response_json, provider_config.response_paths.reply_text)
        input_tokens = resolve_dot_path(response_json, provider_config.response_paths.input_tokens)
        output_tokens = resolve_dot_path(response_json, provider_config.response_paths.output_tokens)
        total_tokens = resolve_dot_path(response_json, provider_config.response_paths.total_tokens)

        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        cost_usd = calculate_cost(provider_name, model, input_tokens, output_tokens)

        log_data = {
            "provider": provider_name,
            "model": model,
            "prompt_text": prompt_text,
            "reply_text": reply_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "status_code": status_code,
        }
        background_tasks.add_task(save_log_to_db, log_data)

        resp_headers = filter_response_headers(upstream_response.headers)
        if should_optimize:
            resp_headers["X-PromptLens-Optimized"] = "true"
            resp_headers["X-PromptLens-Tokens-Saved"] = str(optimized_tokens_saved)

        return Response(
            content=upstream_response.content,
            status_code=status_code,
            headers=resp_headers,
            media_type="application/json",
        )

    except httpx.RequestError as e:
        latency_ms = (time.time() - start_time) * 1000
        log_data = {
            "provider": provider_name,
            "model": model,
            "prompt_text": prompt_text,
            "status_code": 502,
            "error": str(e),
            "latency_ms": latency_ms,
        }
        background_tasks.add_task(save_log_to_db, log_data)
        return JSONResponse(status_code=502, content={"error": f"Upstream request failed: {str(e)}"})
