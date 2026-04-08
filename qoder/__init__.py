# -*- coding: utf-8 -*-

"""
Qoder Gateway - OpenAI-compatible proxy for Qoder CLI.

Endpoints:
    - GET  /           - Health check
    - GET  /health     - Detailed health status
    - GET  /v1/models  - List available models
    - POST /v1/chat/completions - Chat completions
"""

from qoder.config import (
    APP_TITLE,
    APP_VERSION,
    APP_DESCRIPTION,
    QODER_PROXY_API_KEY,
    resolve_model_id,
)
from qoder.cli_client import QoderCliClient, get_cli_client
from qoder.routes import router

__all__ = [
    "APP_TITLE",
    "APP_VERSION",
    "APP_DESCRIPTION",
    "QODER_PROXY_API_KEY",
    "resolve_model_id",
    "QoderCliClient",
    "get_cli_client",
    "router",
]
