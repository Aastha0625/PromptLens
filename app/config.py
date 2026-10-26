import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into os.environ so dynamic API keys can be read by adapter.py
env_path = ".env"
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///promptlens.db"
    
    # Phase 5: Suggestion Engine (Tier 2 LLM Optimizer)
    ENABLE_LLM_REWRITE: bool = False
    OPTIMIZER_PROVIDER: str = "groq"
    OPTIMIZER_MODEL: str = "openai/gpt-oss-20b"
    OPTIMIZER_API_KEY: Optional[str] = None
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
