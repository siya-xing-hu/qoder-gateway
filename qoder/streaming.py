# -*- coding: utf-8 -*-

"""
Streaming logic for converting Qoder API stream to OpenAI format.
"""

import json
import time
from typing import AsyncGenerator, Optional

import httpx
from loguru import logger

from qoder.config import resolve_model_id


def generate_completion_id() -> str:
    """Generates a unique completion ID."""
    import uuid
    return f"chatcmpl-{uuid.uuid4().hex[:24]}"


async def stream_qoder_to_openai(
    response: httpx.Response,
    model: str
) -> AsyncGenerator[str, None]:
    """
    Converts Qoder streaming response to OpenAI SSE format.

    Args:
        response: HTTP response with streaming data
        model: Model name to include in response

    Yields:
        Strings in SSE format
    """
    completion_id = generate_completion_id()
    created_time = int(time.time())
    resolved_model = resolve_model_id(model)

    first_chunk = True
    buffer = ""

    try:
        async for line in response.aiter_lines():
            if not line.strip():
                continue

            if line.startswith("data: "):
                data = line[6:]

                if data == "[DONE]":
                    yield "data: [DONE]\n\n"
                    return

                try:
                    chunk_data = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse SSE data: {data[:100]}")
                    continue

                openai_chunk = convert_to_openai_chunk(
                    chunk_data, completion_id, created_time, resolved_model, first_chunk
                )
                first_chunk = False

                chunk_str = f"data: {json.dumps(openai_chunk, ensure_ascii=False)}\n\n"
                yield chunk_str

            else:
                try:
                    chunk_data = json.loads(line)
                    openai_chunk = convert_to_openai_chunk(
                        chunk_data, completion_id, created_time, resolved_model, first_chunk
                    )
                    first_chunk = False
                    chunk_str = f"data: {json.dumps(openai_chunk, ensure_ascii=False)}\n\n"
                    yield chunk_str
                except json.JSONDecodeError:
                    buffer += line
                    continue

    except httpx.ReadError as e:
        logger.error(f"Stream read error: {e}")
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"Unexpected streaming error: {e}")
        yield "data: [DONE]\n\n"


def convert_to_openai_chunk(
    chunk_data: dict,
    completion_id: str,
    created_time: int,
    model: str,
    is_first: bool
) -> dict:
    """Converts a chunk from Qoder API to OpenAI format."""
    if "choices" in chunk_data:
        chunk = chunk_data.copy()
        chunk["id"] = completion_id
        chunk["created"] = created_time
        chunk["model"] = model
        if is_first and chunk.get("choices"):
            delta = chunk["choices"][0].get("delta", {})
            if "role" not in delta:
                delta["role"] = "assistant"
        return chunk

    if "content" in chunk_data or "text" in chunk_data:
        content = chunk_data.get("content") or chunk_data.get("text", "")
        finish_reason = chunk_data.get("finish_reason")
        delta = {"content": content}
        if is_first:
            delta["role"] = "assistant"
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]
        }

    if "tool_calls" in chunk_data:
        delta = {"tool_calls": chunk_data["tool_calls"]}
        if is_first:
            delta["role"] = "assistant"
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": chunk_data.get("finish_reason")}]
        }

    if "usage" in chunk_data:
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
            "usage": chunk_data["usage"]
        }

    logger.debug(f"Unknown chunk format: {list(chunk_data.keys())}")
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model,
        "choices": [{"index": 0, "delta": chunk_data, "finish_reason": None}]
    }


async def collect_stream_response(
    response: httpx.Response,
    model: str
) -> dict:
    """Collects entire streaming response into a single OpenAI response."""
    completion_id = generate_completion_id()
    created_time = int(time.time())
    resolved_model = resolve_model_id(model)

    full_content = ""
    tool_calls = []
    finish_reason = None
    usage = None

    try:
        async for line in response.aiter_lines():
            if not line.strip():
                continue
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk_data = json.loads(data)
                except json.JSONDecodeError:
                    continue

                if "choices" in chunk_data:
                    choices = chunk_data["choices"]
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_content += content
                        if "tool_calls" in delta:
                            tool_calls.extend(delta["tool_calls"])
                        if choices[0].get("finish_reason"):
                            finish_reason = choices[0]["finish_reason"]

                if "usage" in chunk_data:
                    usage = chunk_data["usage"]

    except Exception as e:
        logger.error(f"Error collecting stream response: {e}")

    message: dict = {"role": "assistant", "content": full_content}
    if tool_calls:
        message["tool_calls"] = tool_calls

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created_time,
        "model": resolved_model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    }
