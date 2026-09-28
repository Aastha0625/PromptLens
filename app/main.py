from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
import httpx
from contextlib import asynccontextmanager

from .database import engine, Base
from .provider_config import providers
from .proxy import handle_proxy_request
from .api import router as api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    app.state.http_client = httpx.AsyncClient(timeout=60.0)
    yield
    await app.state.http_client.aclose()

app = FastAPI(title="PromptLens", lifespan=lifespan)
app.include_router(api_router)

@app.post("/proxy/{provider}")
async def proxy(provider: str, request: Request, background_tasks: BackgroundTasks):
    if provider not in providers:
        raise HTTPException(status_code=404, detail="Unknown provider")
        
    try:
        body = await request.json()
    except Exception:
        body = None
        
    return await handle_proxy_request(
        provider, 
        request, 
        body, 
        background_tasks, 
        app.state.http_client
    )
