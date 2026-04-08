# -*- coding: utf-8 -*-

"""
HTTP client for Qoder API with retry logic support.
"""

import asyncio
from typing import Optional, Dict, Any

import httpx
from fastapi import HTTPException
from loguru import logger

from qoder.config import (
    MAX_RETRIES,
    BASE_RETRY_DELAY,
    STREAMING_READ_TIMEOUT,
    FIRST_TOKEN_MAX_RETRIES,
    get_qoder_chat_url,
)
from qoder.auth import QoderAuthManager


class QoderHttpClient:
    """
    HTTP client for Qoder API with retry logic support.

    Automatically handles errors and retries requests:
    - 401: authentication errors (try to reload token)
    - 429: waits with exponential backoff
    - 5xx: waits with exponential backoff
    - Timeouts: waits with exponential backoff
    """

    def __init__(
        self,
        auth_manager: QoderAuthManager,
        shared_client: Optional[httpx.AsyncClient] = None
    ):
        self.auth_manager = auth_manager
        self._shared_client = shared_client
        self._owns_client = shared_client is None
        self.client: Optional[httpx.AsyncClient] = shared_client

    async def _get_client(self, stream: bool = False) -> httpx.AsyncClient:
        if self._shared_client is not None:
            return self._shared_client

        if self.client is None or self.client.is_closed:
            if stream:
                timeout_config = httpx.Timeout(
                    connect=30.0,
                    read=STREAMING_READ_TIMEOUT,
                    write=30.0,
                    pool=30.0
                )
            else:
                timeout_config = httpx.Timeout(timeout=300.0)

            self.client = httpx.AsyncClient(timeout=timeout_config, follow_redirects=True)
        return self.client

    async def close(self) -> None:
        if not self._owns_client:
            return
        if self.client and not self.client.is_closed:
            try:
                await self.client.aclose()
            except Exception as e:
                logger.warning(f"Error closing HTTP client: {e}")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": self.auth_manager.get_auth_header(),
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if self._streaming_mode else "application/json",
        }

    async def request_with_retry(
        self,
        method: str,
        url: str,
        json_data: Dict[str, Any],
        stream: bool = False
    ) -> httpx.Response:
        self._streaming_mode = stream
        max_retries = FIRST_TOKEN_MAX_RETRIES if stream else MAX_RETRIES

        client = await self._get_client(stream=stream)
        last_error = None

        for attempt in range(max_retries):
            try:
                headers = self._get_headers()

                if stream:
                    headers["Connection"] = "close"
                    req = client.build_request(method, url, json=json_data, headers=headers)
                    response = await client.send(req, stream=True)
                else:
                    response = await client.request(method, url, json=json_data, headers=headers)

                if response.status_code == 200:
                    return response

                if response.status_code == 401:
                    logger.warning(f"Received 401, reloading token (attempt {attempt + 1}/{max_retries})")
                    if self.auth_manager.reload_token():
                        continue
                    raise HTTPException(status_code=401, detail="Qoder API authentication failed.")

                if response.status_code == 403:
                    self.auth_manager.reload_token()
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue

                if response.status_code == 429:
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    logger.warning(f"Received 429, waiting {delay}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                    continue

                if 500 <= response.status_code < 600:
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    logger.warning(f"Received {response.status_code}, waiting {delay}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                    continue

                return response

            except httpx.TimeoutException as e:
                last_error = e
                delay = BASE_RETRY_DELAY * (2 ** attempt)
                logger.warning(f"Request timeout, waiting {delay}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(delay)

            except httpx.RequestError as e:
                last_error = e
                delay = BASE_RETRY_DELAY * (2 ** attempt)
                logger.warning(f"Request error: {e}, waiting {delay}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(delay)

        if last_error:
            raise HTTPException(
                status_code=504 if stream else 502,
                detail=f"Request to Qoder API failed after {max_retries} attempts: {last_error}"
            )
        else:
            raise HTTPException(
                status_code=504 if stream else 502,
                detail=f"Request to Qoder API failed after {max_retries} attempts"
            )

    async def __aenter__(self) -> "QoderHttpClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
