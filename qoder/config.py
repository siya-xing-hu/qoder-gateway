# -*- coding: utf-8 -*-

"""
Qoder Gateway Configuration.

Centralized storage for all settings, constants, and mappings.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()


# ==================================================================================================
# Server Settings
# ==================================================================================================

DEFAULT_SERVER_HOST: str = "0.0.0.0"
SERVER_HOST: str = os.getenv("SERVER_HOST", DEFAULT_SERVER_HOST)

DEFAULT_SERVER_PORT: int = 11435
SERVER_PORT: int = int(os.getenv("SERVER_PORT", str(DEFAULT_SERVER_PORT)))


# ==================================================================================================
# Qoder API Configuration
# ==================================================================================================

QODER_API_BASE_URL: str = os.getenv("QODER_API_BASE_URL", "https://api.qoder.com")
QODER_API_VERSION: str = os.getenv("QODER_API_VERSION", "v1")


# ==================================================================================================
# Authentication Settings
# ==================================================================================================

QODER_PERSONAL_ACCESS_TOKEN: str = os.getenv("QODER_PERSONAL_ACCESS_TOKEN", "")
QODER_CONFIG_FILE: str = os.getenv("QODER_CONFIG_FILE", "")
QODER_PROXY_API_KEY: str = os.getenv("QODER_PROXY_API_KEY", "my-qoder-secret-password-123")


# ==================================================================================================
# Retry Configuration
# ==================================================================================================

MAX_RETRIES: int = 3
BASE_RETRY_DELAY: float = 1.0


# ==================================================================================================
# Timeout Settings
# ==================================================================================================

FIRST_TOKEN_TIMEOUT: float = float(os.getenv("QODER_FIRST_TOKEN_TIMEOUT", "30"))
STREAMING_READ_TIMEOUT: float = float(os.getenv("QODER_STREAMING_READ_TIMEOUT", "300"))
FIRST_TOKEN_MAX_RETRIES: int = int(os.getenv("QODER_FIRST_TOKEN_MAX_RETRIES", "3"))


# ==================================================================================================
# Logging Settings
# ==================================================================================================

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()


# ==================================================================================================
# Database Settings (optional - if not set, logs are only printed to console)
# ==================================================================================================

DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
LOG_TO_DB: bool = DATABASE_URL is not None


# ==================================================================================================
# Model Configuration
# ==================================================================================================

QODER_DEFAULT_MODELS: List[Dict[str, str]] = [
    {"id": "lite", "owned_by": "qoder", "description": "Free tier - Simple Q&A, lightweight tasks"},
    {"id": "efficient", "owned_by": "qoder", "description": "Low cost - Everyday coding, code completion"},
    {"id": "auto", "owned_by": "qoder", "description": "Standard - Complex tasks, multi-step reasoning (default)"},
    {"id": "performance", "owned_by": "qoder", "description": "High cost - Challenging engineering problems, large codebases"},
    {"id": "ultimate", "owned_by": "qoder", "description": "Highest cost - Maximum performance, best possible results"},
]

QODER_MODEL_ALIASES: Dict[str, str] = {
    "claude-sonnet": "auto",
    "claude-sonnet-4": "auto",
    "claude-3.5-sonnet": "auto",
    "gpt-4": "auto",
    "gpt-4o": "auto",
    "claude-opus": "performance",
    "claude-opus-4": "performance",
    "claude-3.5-opus": "performance",
    "claude-opus-4.5": "ultimate",
    "claude-haiku": "efficient",
    "claude-3.5-haiku": "efficient",
    "gpt-4o-mini": "efficient",
    "gpt-3.5-turbo": "lite",
}


# ==================================================================================================
# Application Version
# ==================================================================================================

APP_VERSION: str = "1.0.0"
APP_TITLE: str = "Qoder Gateway"
APP_DESCRIPTION: str = "Proxy gateway for Qoder CLI API. OpenAI compatible."


# ==================================================================================================
# Helper Functions
# ==================================================================================================

def get_qoder_api_url() -> str:
    """Return the full Qoder API URL."""
    base_url = QODER_API_BASE_URL.rstrip("/")
    if QODER_API_VERSION:
        return f"{base_url}/{QODER_API_VERSION}"
    return base_url


def get_qoder_chat_url() -> str:
    """Return the Qoder chat completions URL."""
    return f"{get_qoder_api_url()}/chat/completions"


def get_qoder_models_url() -> str:
    """Return the Qoder models list URL."""
    return f"{get_qoder_api_url()}/models"


def load_token_from_config_file(file_path: Optional[str] = None) -> Optional[str]:
    """
    Load Personal Access Token from Qoder CLI config file.

    Args:
        file_path: Path to config file (default: ~/.qoder.json)

    Returns:
        Token string if found, None otherwise
    """
    if file_path:
        config_path = Path(file_path).expanduser()
    else:
        config_path = Path.home() / ".qoder.json"

    if not config_path.exists():
        return None

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        token_fields = [
            "personalAccessToken",
            "personal_access_token",
            "token",
            "accessToken",
            "access_token",
        ]

        for field in token_fields:
            if field in config and config[field]:
                return config[field]

        if "auth" in config and isinstance(config["auth"], dict):
            for field in token_fields:
                if field in config["auth"] and config["auth"][field]:
                    return config["auth"][field]

        return None

    except (json.JSONDecodeError, IOError) as e:
        from loguru import logger
        logger.warning(f"Failed to load Qoder config from {config_path}: {e}")
        return None


def resolve_model_id(model_name: str) -> str:
    """
    Resolve model name to actual model ID.

    Args:
        model_name: Model name from client request

    Returns:
        Resolved model ID
    """
    return QODER_MODEL_ALIASES.get(model_name, model_name)
