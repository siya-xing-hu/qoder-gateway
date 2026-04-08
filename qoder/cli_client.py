# -*- coding: utf-8 -*-

"""
Qoder CLI Client - Execute qodercli commands.

This module provides a client that interacts with Qoder by executing
qodercli commands directly, rather than using HTTP API.
"""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Any

from loguru import logger

from .config import resolve_model_id


class QoderCliClient:
    """
    Client for executing qodercli commands.

    Runs qodercli as a subprocess and captures its output,
    converting it to OpenAI-compatible format.
    """

    def __init__(self, cli_path: Optional[str] = None):
        """
        Initialize the CLI client.

        Args:
            cli_path: Path to qodercli executable (default: find in PATH)
        """
        self.cli_path = cli_path or self._find_cli()

    def _find_cli(self) -> str:
        """Find qodercli executable in PATH."""
        candidates = [
            "qodercli",
            "qoder",
            "/usr/local/bin/qodercli",
            "/usr/bin/qodercli",
            str(Path.home() / ".local/bin/qodercli"),
            str(Path.home() / ".npm-global/bin/qodercli"),
        ]

        for candidate in candidates:
            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    logger.debug(f"Found qodercli at: {candidate}")
                    return candidate
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

        logger.warning("qodercli not found in common locations, using 'qodercli'")
        return "qodercli"

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "auto",
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        workspace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a chat completion using qodercli.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model tier (lite, efficient, auto, performance, ultimate)
            stream: Whether to stream the response
            temperature: Temperature parameter (not supported by qodercli)
            max_tokens: Max tokens (not supported by qodercli)
            workspace: Working directory for the command

        Returns:
            OpenAI-compatible response dict
        """
        tier = resolve_model_id(model)
        prompt = self._build_prompt(messages)

        cmd = [self.cli_path, "-p"]

        if workspace:
            cmd.extend(["-w", workspace])

        cmd.append(prompt)
        cmd.extend(["--model", tier])

        logger.debug(f"Executing: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace') or "Unknown error"
                logger.error(f"qodercli failed: {error_msg}")
                raise RuntimeError(f"Qoder CLI error: {error_msg}")

            output = stdout.decode('utf-8', errors='replace')
            return self._build_response(output, model)

        except asyncio.TimeoutError:
            logger.error("qodercli command timed out")
            raise RuntimeError("Qoder CLI command timed out")
        except Exception as e:
            logger.error(f"Failed to execute qodercli: {e}")
            raise

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "auto",
        workspace: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Execute a streaming chat completion using qodercli.

        Args:
            messages: List of message dicts
            model: Model tier
            workspace: Working directory

        Yields:
            Text content chunks
        """
        tier = resolve_model_id(model)
        prompt = self._build_prompt(messages)

        cmd = [self.cli_path, "-p"]

        if workspace:
            cmd.extend(["-w", workspace])

        cmd.append(prompt)
        cmd.extend(["--model", tier, "--output-format", "stream-json"])

        logger.debug(f"Executing (streaming): {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            assert process.stdout is not None
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                line_str = line.decode('utf-8', errors='replace').strip()
                if line_str:
                    try:
                        data = json.loads(line_str)

                        if data.get("type") == "assistant" and data.get("subtype") == "message":
                            message = data.get("message", {})
                            content_list = message.get("content", [])
                            for content_item in content_list:
                                if content_item.get("type") == "text":
                                    text = content_item.get("text", "")
                                    if isinstance(text, list):
                                        text = "".join(str(t) for t in text)
                                    elif not isinstance(text, str):
                                        text = str(text)
                                    if text:
                                        yield text

                        elif "content" in data:
                            content = data["content"]
                            if isinstance(content, list):
                                yield "".join(str(c) for c in content)
                            elif isinstance(content, str):
                                yield content
                            else:
                                yield str(content)
                        elif "text" in data:
                            text = data["text"]
                            if isinstance(text, list):
                                yield "".join(str(t) for t in text)
                            elif isinstance(text, str):
                                yield text
                            else:
                                yield str(text)

                    except json.JSONDecodeError:
                        yield line_str

            await process.wait()

            if process.returncode != 0:
                stderr = await process.stderr.read() if process.stderr else b""
                error_msg = stderr.decode('utf-8', errors='replace') or "Unknown error"
                logger.error(f"qodercli failed: {error_msg}")
                raise RuntimeError(f"Qoder CLI error: {error_msg}")

        except Exception as e:
            logger.error(f"Failed to execute qodercli: {e}")
            raise

    def _build_prompt(self, messages: List[Dict[str, Any]]) -> str:
        """Build a prompt string from messages."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        text_parts.append(item)
                content = "".join(text_parts)
            elif not isinstance(content, str):
                content = str(content)

            if role == "system":
                parts.append(f"[System: {content}]")
            elif role == "user":
                parts.append(content)
            elif role == "assistant":
                parts.append(f"[Assistant: {content}]")
            else:
                parts.append(content)

        return "\n\n".join(parts)

    def _build_response(self, output: str, model: str) -> Dict[str, Any]:
        """Build an OpenAI-compatible response from CLI output."""
        import time
        import uuid

        return {
            "id": f"qoder-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": output.strip(),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }

    def is_available(self) -> bool:
        """Check if qodercli is available."""
        try:
            result = subprocess.run(
                [self.cli_path, "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False


# Global client instance
_cli_client: Optional[QoderCliClient] = None


def get_cli_client() -> QoderCliClient:
    """Get or create the global CLI client instance."""
    global _cli_client
    if _cli_client is None:
        _cli_client = QoderCliClient()
    return _cli_client
