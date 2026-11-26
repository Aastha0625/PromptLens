from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.post("/proxy/{provider}")
@app.post("/proxy/{provider}/{subpath:path}")
async def proxy(provider: str, request: Request, background_tasks: BackgroundTasks, subpath: str = ""):
    if provider not in providers:
        raise HTTPException(status_code=404, detail="Unknown provider")
        
    try:
        body = await request.json()
    except Exception:
        body = None

    http_client = getattr(app.state, "http_client", None)
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=60.0)
        
    return await handle_proxy_request(
        provider, 
        request, 
        body, 
        background_tasks, 
        http_client
    )
