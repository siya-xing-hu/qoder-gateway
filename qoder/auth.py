# -*- coding: utf-8 -*-

"""
Authentication manager for Qoder Gateway.

Manages Personal Access Token authentication:
- Loading token from environment variables
- Loading token from config file (~/.qoder.json)
- Token validation
"""

from enum import Enum
from pathlib import Path
from typing import Optional

from loguru import logger

from qoder.config import (
    QODER_PERSONAL_ACCESS_TOKEN,
    QODER_CONFIG_FILE,
    load_token_from_config_file,
)


class AuthSource(Enum):
    """Source of the authentication token."""
    ENVIRONMENT = "environment"
    CONFIG_FILE = "config_file"
    DIRECT = "direct"


class QoderAuthManager:
    """
    Manages authentication for Qoder API.

    Supports Personal Access Token authentication from multiple sources:
    1. Direct token parameter (highest priority)
    2. Environment variable QODER_PERSONAL_ACCESS_TOKEN
    3. Config file ~/.qoder.json
    """

    def __init__(
        self,
        token: Optional[str] = None,
        config_file: Optional[str] = None
    ):
        """
        Initialize the authentication manager.

        Args:
            token: Personal Access Token (optional)
            config_file: Path to Qoder config file (optional, defaults to ~/.qoder.json)
        """
        self._token: Optional[str] = None
        self._auth_source: Optional[AuthSource] = None
        self._config_file = config_file or QODER_CONFIG_FILE

        if token:
            self._token = token
            self._auth_source = AuthSource.DIRECT
            logger.info("Qoder auth: Using directly provided token")
        elif QODER_PERSONAL_ACCESS_TOKEN:
            self._token = QODER_PERSONAL_ACCESS_TOKEN
            self._auth_source = AuthSource.ENVIRONMENT
            logger.info("Qoder auth: Using token from environment variable")
        else:
            loaded_token = load_token_from_config_file(self._config_file)
            if loaded_token:
                self._token = loaded_token
                self._auth_source = AuthSource.CONFIG_FILE
                config_path = self._config_file or "~/.qoder.json"
                logger.info(f"Qoder auth: Using token from config file ({config_path})")

        if not self._token:
            logger.warning(
                "Qoder auth: No Personal Access Token configured. "
                "Set QODER_PERSONAL_ACCESS_TOKEN environment variable or "
                "create ~/.qoder.json config file."
            )

    def get_token(self) -> str:
        """Returns the Personal Access Token."""
        if not self._token:
            raise ValueError(
                "Qoder Personal Access Token not configured. "
                "Please set QODER_PERSONAL_ACCESS_TOKEN environment variable "
                "or create ~/.qoder.json config file with your token. "
                "Get your token from: https://qoder.com/account/integrations"
            )
        return self._token

    def is_configured(self) -> bool:
        """Check if authentication is configured."""
        return bool(self._token)

    @property
    def auth_source(self) -> Optional[AuthSource]:
        """Returns the source of the authentication token."""
        return self._auth_source

    def reload_token(self) -> bool:
        """
        Reload token from configuration sources.

        Returns:
            True if token was successfully reloaded, False otherwise
        """
        loaded_token = load_token_from_config_file(self._config_file)
        if loaded_token:
            self._token = loaded_token
            self._auth_source = AuthSource.CONFIG_FILE
            logger.info("Qoder auth: Token reloaded from config file")
            return True

        if QODER_PERSONAL_ACCESS_TOKEN:
            self._token = QODER_PERSONAL_ACCESS_TOKEN
            self._auth_source = AuthSource.ENVIRONMENT
            logger.info("Qoder auth: Token reloaded from environment variable")
            return True

        logger.warning("Qoder auth: Failed to reload token - no token found in config sources")
        return False

    def get_auth_header(self) -> str:
        """Returns the Authorization header value."""
        return f"Bearer {self.get_token()}"
