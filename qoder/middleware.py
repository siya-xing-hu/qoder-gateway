# -*- coding: utf-8 -*-

"""
Request/Response logging middleware.

Intercepts all /v1/ requests, logs timing, status, and request details.
Always logs to console via loguru; persists to database if configured.
"""

import json
import time
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import StreamingResponse
from loguru import logger

from qoder.database import save_log


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all /v1/ API requests and responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Only log /v1/ API requests
        if not path.startswith("/v1/"):
            return await call_next(request)

        method = request.method
        client_ip = request.client.host if request.client else "unknown"
        start_time = time.time()

        # Extract request body info
        request_model = None
        request_messages_count = None
        request_stream = None
        request_body_text = None

        try:
            body_bytes = await request.body()
            if body_bytes:
                request_body_text = body_bytes.decode("utf-8")
                body_json = json.loads(request_body_text)
                request_model = body_json.get("model")
                messages = body_json.get("messages")
                if isinstance(messages, list):
                    request_messages_count = len(messages)
                request_stream = body_json.get("stream", False)
        except Exception:
            pass

        # Call the actual endpoint
        status_code = 500
        response_summary = None
        error_message = None

        try:
            response = await call_next(request)
            status_code = response.status_code

            # For non-streaming responses, capture response summary
            if not isinstance(response, StreamingResponse) or "text/event-stream" not in (response.media_type or ""):
                # Read and re-create the response body
                response_body = b""
                async for chunk in response.body_iterator:
                    if isinstance(chunk, str):
                        response_body += chunk.encode("utf-8")
                    else:
                        response_body += chunk

                try:
                    body_text = response_body.decode("utf-8")
                    if len(body_text) > 500:
                        response_summary = body_text[:500] + "..."
                    else:
                        response_summary = body_text
                except Exception:
                    response_summary = f"<binary {len(response_body)} bytes>"

                # Re-create the response with the same body
                from starlette.responses import Response as StarletteResponse
                response = StarletteResponse(
                    content=response_body,
                    status_code=status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )

            duration_ms = (time.time() - start_time) * 1000

            # Console log
            stream_tag = " [stream]" if request_stream else ""
            model_tag = f" model={request_model}" if request_model else ""
            logger.info(
                f"{method} {path} -> {status_code} ({duration_ms:.0f}ms)"
                f"{model_tag}{stream_tag}"
            )

            # Database log
            await save_log(
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
                request_model=request_model,
                request_messages_count=request_messages_count,
                request_stream=request_stream,
                request_body=request_body_text,
                response_summary=response_summary,
            )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_message = str(e)

            logger.error(
                f"{method} {path} -> ERROR ({duration_ms:.0f}ms): {error_message}"
            )

            await save_log(
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
                request_model=request_model,
                request_messages_count=request_messages_count,
                request_stream=request_stream,
                request_body=request_body_text,
                error_message=error_message,
            )

            raise
