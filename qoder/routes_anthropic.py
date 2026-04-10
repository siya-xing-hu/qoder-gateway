# -*- coding: utf-8 -*-

"""
FastAPI routes for Anthropic Messages API.

Contains the /v1/messages endpoint compatible with Anthropic's Messages API.
Translates Anthropic format requests to qodercli commands and returns responses
in Anthropic format.

Reference: https://docs.anthropic.com/en/api/messages
"""

import json
import time
import uuid
from typing import Optional, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, Security, Header
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import APIKeyHeader
from loguru import logger

from qoder.config import QODER_PROXY_API_KEY, QODER_WORKSPACE, resolve_model_id
from qoder.cli_client import get_cli_client, QoderCliClient
from qoder.models_anthropic import (
    AnthropicMessagesRequest,
    AnthropicMessagesResponse,
    AnthropicMessage,
    AnthropicUsage,
    TextContentBlock,
    ThinkingContentBlock,
    ToolUseContentBlock,
    AnthropicErrorResponse,
    AnthropicErrorDetail,
)


# --- Security scheme ---
# Anthropic uses x-api-key header instead of Authorization: Bearer
anthropic_api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)
# Also support Authorization: Bearer for compatibility
auth_header = APIKeyHeader(name="Authorization", auto_error=False)


async def verify_anthropic_api_key(
    x_api_key: Optional[str] = Security(anthropic_api_key_header),
    authorization: Optional[str] = Security(auth_header)
) -> bool:
    """
    Verify API key for Anthropic API.

    Supports two authentication methods:
    1. x-api-key header (Anthropic native)
    2. Authorization: Bearer header (for compatibility)

    Args:
        x_api_key: Value from x-api-key header
        authorization: Value from Authorization header

    Returns:
        True if key is valid

    Raises:
        HTTPException: 401 if key is invalid or missing
    """
    # Check x-api-key first (Anthropic native)
    if x_api_key and x_api_key == QODER_PROXY_API_KEY:
        return True

    # Fall back to Authorization: Bearer
    if authorization and authorization == f"Bearer {QODER_PROXY_API_KEY}":
        return True

    logger.warning("Access attempt with invalid API key (Anthropic endpoint)")
    raise HTTPException(
        status_code=401,
        detail={
            "type": "error",
            "error": {
                "type": "authentication_error",
                "message": "Invalid or missing API key. Use x-api-key header or Authorization: Bearer."
            }
        }
    )


# --- Router ---
router = APIRouter(tags=["Anthropic API"])


def extract_system_prompt(system: Any) -> str:
    """
    Extract system prompt text from Anthropic system field.

    Anthropic API supports system in two formats:
    1. String: "You are helpful"
    2. List of content blocks: [{"type": "text", "text": "...", "cache_control": {...}}]

    Args:
        system: System prompt in string or list format

    Returns:
        Extracted system prompt as string
    """
    if system is None:
        return ""

    if isinstance(system, str):
        return system

    if isinstance(system, list):
        text_parts = []
        for block in system:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            elif hasattr(block, "type") and block.type == "text":
                text_parts.append(getattr(block, "text", ""))
        return "\n".join(text_parts)

    return str(system)


def extract_text_from_content(content: Any) -> str:
    """
    Extract text content from Anthropic message content.

    Anthropic content can be:
    - String: "Hello, world!"
    - List of content blocks: [{"type": "text", "text": "Hello"}]

    Args:
        content: Anthropic message content

    Returns:
        Extracted text content
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            elif hasattr(block, "type") and block.type == "text":
                text_parts.append(block.text)
        return "".join(text_parts)

    return str(content) if content else ""


def convert_anthropic_messages_to_openai(
    messages: List[AnthropicMessage],
    system_prompt: str
) -> List[Dict[str, str]]:
    """
    Convert Anthropic messages to OpenAI format for qodercli.

    Args:
        messages: List of Anthropic messages
        system_prompt: System prompt string

    Returns:
        List of OpenAI-style message dicts
    """
    openai_messages = []

    # Add system prompt if present
    if system_prompt:
        openai_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        text_content = extract_text_from_content(msg.content)
        openai_messages.append({
            "role": msg.role,
            "content": text_content
        })

    return openai_messages


@router.post("/v1/messages", dependencies=[Depends(verify_anthropic_api_key)])
async def messages(
    request: Request,
    request_data: AnthropicMessagesRequest,
    anthropic_version: Optional[str] = Header(None, alias="anthropic-version")
):
    """
    Anthropic Messages API endpoint.

    Compatible with Anthropic's /v1/messages endpoint.
    Accepts requests in Anthropic format and executes qodercli commands.

    Required headers:
    - x-api-key: Your API key (or Authorization: Bearer)
    - anthropic-version: API version (optional, for compatibility)
    - Content-Type: application/json

    Args:
        request: FastAPI Request
        request_data: Request in Anthropic MessagesRequest format
        anthropic_version: Anthropic API version header (optional)

    Returns:
        StreamingResponse for streaming mode (SSE)
        JSONResponse for non-streaming mode

    Raises:
        HTTPException: On validation or API errors
    """
    logger.info(f"Request to /v1/messages (model={request_data.model}, stream={request_data.stream})")

    if anthropic_version:
        logger.debug(f"Anthropic-Version header: {anthropic_version}")

    cli_client = get_cli_client()

    if not cli_client.is_available():
        raise HTTPException(
            status_code=503,
            detail={
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": "qodercli command not found. Please install Qoder CLI: https://docs.qoder.com/cli"
                }
            }
        )

    # Extract system prompt
    system_prompt = extract_system_prompt(request_data.system)

    # Convert Anthropic messages to OpenAI format for qodercli
    openai_messages = convert_anthropic_messages_to_openai(
        request_data.messages,
        system_prompt
    )

    # Resolve model to qodercli model tier
    model_tier = resolve_model_id(request_data.model)

    try:
        if request_data.stream:
            async def stream_wrapper():
                """Generate SSE stream from CLI output in Anthropic format."""
                try:
                    message_id = f"msg_{uuid.uuid4().hex[:24]}"
                    created = int(time.time())

                    # Build initial message for message_start
                    initial_message = {
                        "id": message_id,
                        "type": "message",
                        "role": "assistant",
                        "model": request_data.model,
                        "content": [],
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {"input_tokens": 0, "output_tokens": 0}
                    }

                    # message_start event
                    message_start = {
                        "type": "message_start",
                        "message": initial_message
                    }
                    yield f"event: message_start\ndata: {json.dumps(message_start)}\n\n"

                    # content_block_start event
                    content_block_start = {
                        "type": "content_block_start",
                        "index": 0,
                        "content_block": {"type": "text", "text": ""}
                    }
                    yield f"event: content_block_start\ndata: {json.dumps(content_block_start)}\n\n"

                    # Stream content deltas
                    output_tokens = 0
                    async for content in cli_client.chat_completion_stream(
                        messages=openai_messages,
                        model=model_tier,
                        workspace=QODER_WORKSPACE,
                    ):
                        output_tokens += 1  # rough estimate
                        content_block_delta = {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {"type": "text_delta", "text": content}
                        }
                        yield f"event: content_block_delta\ndata: {json.dumps(content_block_delta)}\n\n"

                    # content_block_stop event
                    content_block_stop = {
                        "type": "content_block_stop",
                        "index": 0
                    }
                    yield f"event: content_block_stop\ndata: {json.dumps(content_block_stop)}\n\n"

                    # message_delta event
                    message_delta = {
                        "type": "message_delta",
                        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                        "usage": {"output_tokens": output_tokens}
                    }
                    yield f"event: message_delta\ndata: {json.dumps(message_delta)}\n\n"

                    # message_stop event
                    message_stop = {"type": "message_stop"}
                    yield f"event: message_stop\ndata: {json.dumps(message_stop)}\n\n"

                    logger.info("POST /v1/messages (streaming) - completed")

                except Exception as e:
                    logger.error(f"Streaming error: {e}")
                    # Send error event
                    error_event = {
                        "type": "error",
                        "error": {"type": "api_error", "message": str(e)}
                    }
                    yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
                    raise

            return StreamingResponse(
                stream_wrapper(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )

        else:
            # Non-streaming mode
            response = await cli_client.chat_completion(
                messages=openai_messages,
                model=model_tier,
                stream=False,
                temperature=request_data.temperature,
                max_tokens=request_data.max_tokens,
                workspace=QODER_WORKSPACE,
            )

            # Extract response text
            response_text = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Build Anthropic-compatible response
            content_blocks = [TextContentBlock(type="text", text=response_text.strip())]

            anthropic_response = AnthropicMessagesResponse(
                id=f"msg_{uuid.uuid4().hex[:24]}",
                type="message",
                role="assistant",
                content=content_blocks,
                model=request_data.model,
                stop_reason="end_turn",
                stop_sequence=None,
                usage=AnthropicUsage(
                    input_tokens=0,
                    output_tokens=0,
                )
            )

            logger.info("POST /v1/messages (non-streaming) - completed")

            return JSONResponse(content=anthropic_response.model_dump())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": f"Internal Server Error: {str(e)}"
                }
            }
        )
