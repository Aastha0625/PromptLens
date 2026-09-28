import yaml
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, Optional

class ProviderResponsePaths(BaseModel):
    reply_text: str
    input_tokens: Optional[str]
    output_tokens: Optional[str]
    total_tokens: Optional[str]

class ProviderConfig(BaseModel):
    base_url: str
    chat_path: str
    default_model: Optional[str] = None
    auth_style: str
    env_var: Optional[str] = None
    extra_headers: Optional[Dict[str, str]] = None
    request_extractor: str
    response_paths: ProviderResponsePaths

providers: Dict[str, ProviderConfig] = {}

def load_providers():
    providers_dir = Path(__file__).parent.parent / "providers"
    for yaml_file in providers_dir.glob("*.yaml"):
        provider_name = yaml_file.stem
        with open(yaml_file, "r") as f:
            data = yaml.safe_load(f)
            providers[provider_name] = ProviderConfig(**data)

load_providers()
