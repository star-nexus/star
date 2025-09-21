import os
import json
import toml
# 配置 rich 库
from rich.console import Console
from rich import print_json

def load_config(config_path: str = ".configs.toml", provider: str = "vllm"):
    """Load LLM configuration from config file"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    config = toml.load(config_path)
    try:
        provider_config = config[provider]
    except KeyError:
        raise ValueError(f"Invalid provider: {provider}")

    print("provider config:")
    print("provider_config python type:", type(provider_config))
    print_json(json.dumps(provider_config))

    try:
        model_id = provider_config["model_id"]
    except KeyError:
        raise ValueError(f"Model ID not found for {provider}")
    
    api_key = provider_config.get("api_key", "EMPTY")
    base_url = provider_config.get("base_url", "")
    
    print(f"Provider: {provider}")
    print(f"Model ID: {model_id}")
    print(f"API Key: {api_key}")
    print(f"Base URL: {base_url}")

if __name__ == "__main__":
    load_config()