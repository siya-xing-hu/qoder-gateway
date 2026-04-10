# -*- coding: utf-8 -*-

"""
Request/Response logging middleware.

Intercepts all /v1/ requests, logs timing, status, and request details.
Always logs to console via loguru; persists to database if configured.

Two-phase database logging:
  Phase 1: Save request immediately when it arrives (completed=False)
  Phase 2: Update with response data when response is complete (completed=True)

For streaming responses:
  - Wraps the SSE iterator to collect all content chunks
  - Logs progress every STREAM_LOG_INTERVAL seconds
  - Merges final content into response_summary after stream ends
"""

import json
import time
from typing import Optional, AsyncIterator

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import StreamingResponse
from loguru import logger

from qoder.config import STREAM_LOG_INTERVAL
from qoder.database import save_request, update_response


def _extract_sse_content(chunk_text: str) -> Optional[str]:
    """Extract text content from an SSE data line.

    Supports both OpenAI and Anthropic SSE formats.
    """
    for line in chunk_text.strip().split("\n"):
        line = line.strip()
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            return None
        try:
            obj = json.loads(data)

            # OpenAI format: choices[0].delta.content
            choices = obj.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content")
                if content:
                    return content

            # Anthropic format: content_block_delta.delta.text
            if obj.get("type") == "content_block_delta":
                delta = obj.get("delta", {})
                if delta.get("type") == "text_delta":
                    return delta.get("text")

        except (json.JSONDecodeError, IndexError, KeyError):
            pass
    return None


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

        # Phase 1: Save request immediately
        log_id = await save_request(
            method=method,
            path=path,
            client_ip=client_ip,
            request_model=request_model,
            request_messages_count=request_messages_count,
            request_stream=request_stream,
            request_body=request_body_text,
        )

        # Call the actual endpoint
        status_code = 500
        response_summary = None
        error_message = None

        try:
            response = await call_next(request)
            status_code = response.status_code

            # Check if this is a streaming SSE response
            is_sse = isinstance(response, StreamingResponse) and "text/event-stream" in (response.media_type or "")

            if is_sse:
                # Wrap the SSE iterator to collect content and log progress
                wrapped = self._wrap_sse_iterator(
                    response.body_iterator,
                    log_id=log_id,
                    status_code=status_code,
                    start_time=start_time,
                    method=method,
                    path=path,
                    request_model=request_model,
                )
                response.body_iterator = wrapped
                return response

            else:
                # Non-streaming: capture full response body
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

                from starlette.responses import Response as StarletteResponse
                response = StarletteResponse(
                    content=response_body,
                    status_code=status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )

                duration_ms = (time.time() - start_time) * 1000

                # Console log
                model_tag = f" model={request_model}" if request_model else ""
                logger.info(
                    f"{method} {path} -> {status_code} ({duration_ms:.0f}ms){model_tag}"
                )

                # Phase 2: Update with response data
                await update_response(
                    log_id=log_id,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    response_summary=response_summary,
                )

                return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_message = str(e)

            logger.error(
                f"{method} {path} -> ERROR ({duration_ms:.0f}ms): {error_message}"
            )

            # Phase 2: Update with error data
            await update_response(
                log_id=log_id,
                status_code=status_code,
                duration_ms=duration_ms,
                error_message=error_message,
            )

            raise

    async def _wrap_sse_iterator(
        self,
        original_iterator: AsyncIterator,
        log_id: Optional[int],
        status_code: int,
        start_time: float,
        method: str,
        path: str,
        request_model: Optional[str],
    ) -> AsyncIterator:
        """
        Wrap an SSE body iterator to:
        1. Collect all content chunks into merged text
        2. Log progress every STREAM_LOG_INTERVAL seconds
        3. Update database with final merged content after stream ends
        """
        collected_content = []
        chunk_count = 0
        last_log_time = time.time()
        total_chars = 0

        try:
            async for chunk in original_iterator:
                # Pass through to client
                yield chunk

                # Extract content from SSE chunk
                chunk_text = chunk if isinstance(chunk, str) else chunk.decode("utf-8", errors="ignore")
                content = _extract_sse_content(chunk_text)
                if content:
                    collected_content.append(content)
                    chunk_count += 1
                    total_chars += len(content)

                # Periodic progress log
                now = time.time()
                if now - last_log_time >= STREAM_LOG_INTERVAL:
                    elapsed_ms = (now - start_time) * 1000
                    model_tag = f" model={request_model}" if request_model else ""
                    logger.info(
                        f"{method} {path} [stream] {chunk_count} chunks, "
                        f"{total_chars} chars, {elapsed_ms:.0f}ms elapsed{model_tag}"
                    )
                    last_log_time = now

        except Exception as e:
            # Stream error
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"{method} {path} [stream] ERROR after {chunk_count} chunks ({duration_ms:.0f}ms): {e}"
            )
            await update_response(
                log_id=log_id,
                status_code=500,
                duration_ms=duration_ms,
                response_summary="".join(collected_content)[:2000] if collected_content else None,
                error_message=str(e),
            )
            raise

        # Stream completed — merge content and update database
        duration_ms = (time.time() - start_time) * 1000
        merged_content = "".join(collected_content)

        if len(merged_content) > 2000:
            response_summary = merged_content[:2000] + "..."
        else:
            response_summary = merged_content or None

        model_tag = f" model={request_model}" if request_model else ""
        logger.info(
            f"{method} {path} -> {status_code} [stream] completed "
            f"({duration_ms:.0f}ms, {chunk_count} chunks, {total_chars} chars){model_tag}"
        )

        await update_response(
            log_id=log_id,
            status_code=status_code,
            duration_ms=duration_ms,
            response_summary=response_summary,
        )
