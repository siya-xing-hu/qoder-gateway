# -*- coding: utf-8 -*-

"""
Qoder Gateway - Main entry point.

OpenAI-compatible proxy server for Qoder CLI.
"""

import argparse
import os
import sys

import uvicorn
from fastapi import FastAPI
from loguru import logger

from qoder.config import (
    APP_TITLE,
    APP_VERSION,
    APP_DESCRIPTION,
    SERVER_HOST,
    SERVER_PORT,
    LOG_LEVEL,
    LOG_DIR,
    QODER_PROXY_API_KEY,
)
from qoder.routes import router
from qoder.cli_client import get_cli_client
from qoder.middleware import RequestLoggingMiddleware
from qoder.database import init_db, close_db


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        description=APP_DESCRIPTION,
    )

    # Include routes
    app.include_router(router)

    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    @app.on_event("startup")
    async def startup_event():
        """Application startup tasks."""
        # Configure loguru file logging
        if LOG_DIR:
            try:
                os.makedirs(LOG_DIR, exist_ok=True)
                logger.add(
                    os.path.join(LOG_DIR, "qoder-gateway_{time:YYYY-MM-DD}.log"),
                    level=LOG_LEVEL,
                    rotation="00:00",
                    retention="30 days",
                    compression="gz",
                    encoding="utf-8",
                )
                logger.info(f"File logging enabled: {LOG_DIR}/")
            except PermissionError:
                logger.warning(f"No write permission to {LOG_DIR}, file logging disabled")

        # Initialize database (no-op if DATABASE_URL not set)
        await init_db()

        logger.info(f"Starting {APP_TITLE} v{APP_VERSION}")
        logger.info(f"API Key: {'configured' if QODER_PROXY_API_KEY else 'NOT SET'}")

        # Check qodercli availability
        cli_client = get_cli_client()
        if cli_client.is_available():
            logger.info("qodercli: available")
        else:
            logger.warning(
                "qodercli: NOT FOUND - Please install Qoder CLI. "
                "See: https://docs.qoder.com/cli"
            )

    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown tasks."""
        await close_db()
        logger.info("Application shutdown complete")

    return app


app = create_app()


def main():
    """Run the server from command line."""
    parser = argparse.ArgumentParser(description=APP_DESCRIPTION)
    parser.add_argument("--host", default=SERVER_HOST, help=f"Host (default: {SERVER_HOST})")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help=f"Port (default: {SERVER_PORT})")
    parser.add_argument("--log-level", default=LOG_LEVEL.lower(), help=f"Log level (default: {LOG_LEVEL})")

    args = parser.parse_args()

    # Configure loguru
    logger.remove()
    logger.add(sys.stderr, level=args.log_level.upper())

    # Add file logging
    if LOG_DIR:
        os.makedirs(LOG_DIR, exist_ok=True)
        logger.add(
            os.path.join(LOG_DIR, "qoder-gateway_{time:YYYY-MM-DD}.log"),
            level=args.log_level.upper(),
            rotation="00:00",
            retention="30 days",
            compression="gz",
            encoding="utf-8",
        )
        logger.info(f"File logging enabled: {LOG_DIR}/")

    logger.info(f"Starting server at http://{args.host}:{args.port}")

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
