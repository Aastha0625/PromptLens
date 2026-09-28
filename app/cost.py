import yaml
from pathlib import Path
from typing import Optional

pricing_data = {}

def load_pricing():
    global pricing_data
    pricing_file = Path(__file__).parent.parent / "pricing.yaml"
    if pricing_file.exists():
        with open(pricing_file, "r") as f:
            data = yaml.safe_load(f)
            if data and "models" in data:
                pricing_data = data["models"]

load_pricing()

from .provider_config import providers

def calculate_cost(provider: str, model: str, input_tokens: Optional[int], output_tokens: Optional[int]) -> Optional[float]:
    if input_tokens is None or output_tokens is None:
        return None
        
    if provider == "ollama" or (provider in providers and providers[provider].is_free_tier):
        return 0.0
        
    if not model or model not in pricing_data:
        return None
        
    pricing = pricing_data[model]
    input_cost = (input_tokens / 1_000_000.0) * pricing.get("input", 0.0)
    output_cost = (output_tokens / 1_000_000.0) * pricing.get("output", 0.0)
    return input_cost + output_cost
