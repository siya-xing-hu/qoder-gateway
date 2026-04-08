# -*- coding: utf-8 -*-

"""
FastAPI routes for Qoder Gateway.

Endpoints:
- / and /health: Health check
- /v1/models: Models list
- /v1/chat/completions: Chat completions
"""

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Security, Query
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.security import APIKeyHeader
from fastapi.templating import Jinja2Templates
from loguru import logger

from qoder.config import (
    QODER_PROXY_API_KEY,
    QODER_DEFAULT_MODELS,
    APP_VERSION,
)
from qoder.models import (
    OpenAIModel,
    ModelList,
    ChatCompletionRequest,
)
from qoder.cli_client import get_cli_client, QoderCliClient
from qoder.converters import validate_request
from qoder.database import get_logs, is_db_available


# --- Security scheme ---
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

# --- Templates ---
_templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


async def verify_api_key(auth_header: str = Security(api_key_header)) -> bool:
    """Verify API key in Authorization header."""
    if not auth_header or auth_header != f"Bearer {QODER_PROXY_API_KEY}":
        logger.warning("Access attempt with invalid API key for Qoder proxy.")
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    return True


# --- Router ---
router = APIRouter()


@router.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "Qoder Gateway is running",
        "version": APP_VERSION
    }


@router.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": APP_VERSION
    }


@router.get("/v1/models", response_model=ModelList, dependencies=[Depends(verify_api_key)])
async def get_models(request: Request):
    """Return list of available models."""
    logger.info("Request to /v1/models")

    openai_models = [
        OpenAIModel(
            id=model["id"],
            owned_by=model.get("owned_by", "qoder"),
            description=model.get("description")
        )
        for model in QODER_DEFAULT_MODELS
    ]

    return ModelList(data=openai_models)


@router.post("/v1/chat/completions", dependencies=[Depends(verify_api_key)])
async def chat_completions(request: Request, request_data: ChatCompletionRequest):
    """
    Chat completions endpoint - compatible with OpenAI API.

    Accepts requests in OpenAI format and executes qodercli command.
    """
    logger.info(f"Request to /v1/chat/completions (model={request_data.model}, stream={request_data.stream})")

    cli_client = get_cli_client()

    if not cli_client.is_available():
        raise HTTPException(
            status_code=503,
            detail="qodercli command not found. Please install Qoder CLI: https://docs.qoder.com/cli"
        )

    validation_error = validate_request(request_data)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    messages = []
    for msg in request_data.messages:
        messages.append({
            "role": msg.role,
            "content": msg.content
        })

    try:
        if request_data.stream:
            async def stream_wrapper():
                """Generate SSE stream from CLI output."""
                try:
                    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
                    created = int(time.time())

                    initial_chunk = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": request_data.model,
                        "choices": [{
                            "index": 0,
                            "delta": {"role": "assistant"},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(initial_chunk)}\n\n"

                    async for content in cli_client.chat_completion_stream(
                        messages=messages,
                        model=request_data.model,
                    ):
                        chunk = {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": request_data.model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": content},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"

                    final_chunk = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": request_data.model,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }]
                    }
                    yield f"data: {json.dumps(final_chunk)}\n\n"
                    yield "data: [DONE]\n\n"

                    logger.info("POST /v1/chat/completions (streaming) - completed")

                except Exception as e:
                    logger.error(f"Streaming error: {e}")
                    raise

            return StreamingResponse(stream_wrapper(), media_type="text/event-stream")

        else:
            response = await cli_client.chat_completion(
                messages=messages,
                model=request_data.model,
                stream=False,
                temperature=request_data.temperature,
                max_tokens=request_data.max_tokens,
            )

            logger.info("POST /v1/chat/completions (non-streaming) - completed")

            return JSONResponse(content=response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# ==================================================================================================
# Log Viewer Endpoints
# ==================================================================================================

@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Render the logs viewer page."""
    return templates.TemplateResponse(
        request=request,
        name="logs.html",
        context={"db_available": is_db_available()},
    )


@router.get("/api/logs")
async def api_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_code: Optional[int] = Query(None),
    path: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
):
    """Return request logs as JSON for the viewer page."""
    if not is_db_available():
        return JSONResponse(
            content={"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0,
                     "message": "Database not configured. Set DATABASE_URL to enable log persistence."},
        )

    result = await get_logs(
        page=page,
        page_size=page_size,
        status_code=status_code,
        path_filter=path,
        model_filter=model,
    )
    return JSONResponse(content=result)
