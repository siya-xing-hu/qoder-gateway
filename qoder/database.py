# -*- coding: utf-8 -*-

"""
Database module for request logging.

When DATABASE_URL is configured, logs are persisted to PostgreSQL.
Otherwise, all functions are no-ops.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from loguru import logger
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Boolean,
    MetaData, Table, create_engine, desc,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from qoder.config import DATABASE_URL, LOG_TO_DB


metadata = MetaData()

request_logs = Table(
    "request_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("timestamp", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    Column("method", String(10)),
    Column("path", String(512)),
    Column("status_code", Integer, nullable=True),
    Column("duration_ms", Float, nullable=True),
    Column("client_ip", String(45)),
    Column("request_model", String(64), nullable=True),
    Column("request_messages_count", Integer, nullable=True),
    Column("request_stream", Boolean, nullable=True),
    Column("request_body", Text, nullable=True),
    Column("response_summary", Text, nullable=True),
    Column("error_message", Text, nullable=True),
    Column("completed", Boolean, default=False),
)

# Engine and session factory (initialized lazily)
_engine = None
_async_session_factory = None


async def init_db() -> None:
    """Initialize database connection and create tables if needed."""
    global _engine, _async_session_factory

    if not LOG_TO_DB:
        logger.info("DATABASE_URL not configured, request logs will only be printed to console")
        return

    try:
        _engine = create_async_engine(DATABASE_URL, echo=False, pool_size=5, max_overflow=10)
        _async_session_factory = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

        # Create tables
        async with _engine.begin() as conn:
            await conn.run_sync(metadata.create_all)

        logger.info("Database initialized, request logs will be persisted to PostgreSQL")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        _engine = None
        _async_session_factory = None


async def close_db() -> None:
    """Close database connection."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None


def is_db_available() -> bool:
    """Check if the database is available."""
    return _engine is not None and _async_session_factory is not None


async def save_log(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    client_ip: str,
    request_model: Optional[str] = None,
    request_messages_count: Optional[int] = None,
    request_stream: Optional[bool] = None,
    request_body: Optional[str] = None,
    response_summary: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Save a complete request log entry to the database (one-shot)."""
    if not is_db_available():
        return

    try:
        async with _async_session_factory() as session:
            await session.execute(
                request_logs.insert().values(
                    timestamp=datetime.now(timezone.utc),
                    method=method,
                    path=path,
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2),
                    client_ip=client_ip,
                    request_model=request_model,
                    request_messages_count=request_messages_count,
                    request_stream=request_stream,
                    request_body=request_body[:10000] if request_body else None,
                    response_summary=response_summary[:2000] if response_summary else None,
                    error_message=error_message[:2000] if error_message else None,
                )
            )
            await session.commit()
    except Exception as e:
        logger.warning(f"Failed to save request log to database: {e}")


async def save_request(
    method: str,
    path: str,
    client_ip: str,
    request_model: Optional[str] = None,
    request_messages_count: Optional[int] = None,
    request_stream: Optional[bool] = None,
    request_body: Optional[str] = None,
) -> Optional[int]:
    """
    Save the request part immediately when a request arrives.

    Returns:
        The log entry ID, or None if save failed.
    """
    if not is_db_available():
        return None

    try:
        async with _async_session_factory() as session:
            result = await session.execute(
                request_logs.insert().values(
                    timestamp=datetime.now(timezone.utc),
                    method=method,
                    path=path,
                    client_ip=client_ip,
                    request_model=request_model,
                    request_messages_count=request_messages_count,
                    request_stream=request_stream,
                    request_body=request_body[:10000] if request_body else None,
                    completed=False,
                )
            )
            await session.commit()
            return result.inserted_primary_key[0]
    except Exception as e:
        logger.warning(f"Failed to save request log: {e}")
        return None


async def update_response(
    log_id: int,
    status_code: int,
    duration_ms: float,
    response_summary: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Update an existing log entry with response data."""
    if not is_db_available() or log_id is None:
        return

    try:
        from sqlalchemy import update
        async with _async_session_factory() as session:
            await session.execute(
                update(request_logs)
                .where(request_logs.c.id == log_id)
                .values(
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2),
                    response_summary=response_summary[:2000] if response_summary else None,
                    error_message=error_message[:2000] if error_message else None,
                    completed=True,
                )
            )
            await session.commit()
    except Exception as e:
        logger.warning(f"Failed to update response log (id={log_id}): {e}")


async def get_logs(
    page: int = 1,
    page_size: int = 50,
    status_code: Optional[int] = None,
    path_filter: Optional[str] = None,
    model_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query request logs with pagination and filtering.

    Returns:
        Dict with 'items', 'total', 'page', 'page_size', 'pages'
    """
    if not is_db_available():
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}

    try:
        async with _async_session_factory() as session:
            from sqlalchemy import select, func

            # Build base query
            query = select(request_logs)
            count_query = select(func.count()).select_from(request_logs)

            # Apply filters
            if status_code is not None:
                query = query.where(request_logs.c.status_code == status_code)
                count_query = count_query.where(request_logs.c.status_code == status_code)
            if path_filter:
                query = query.where(request_logs.c.path.contains(path_filter))
                count_query = count_query.where(request_logs.c.path.contains(path_filter))
            if model_filter:
                query = query.where(request_logs.c.request_model == model_filter)
                count_query = count_query.where(request_logs.c.request_model == model_filter)

            # Get total count
            total_result = await session.execute(count_query)
            total = total_result.scalar() or 0

            # Get paginated results
            offset = (page - 1) * page_size
            query = query.order_by(desc(request_logs.c.id)).offset(offset).limit(page_size)
            result = await session.execute(query)
            rows = result.fetchall()

            items = []
            for row in rows:
                items.append({
                    "id": row.id,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "method": row.method,
                    "path": row.path,
                    "status_code": row.status_code,
                    "duration_ms": row.duration_ms,
                    "client_ip": row.client_ip,
                    "request_model": row.request_model,
                    "request_messages_count": row.request_messages_count,
                    "request_stream": row.request_stream,
                    "request_body": row.request_body,
                    "response_summary": row.response_summary,
                    "error_message": row.error_message,
                    "completed": row.completed,
                })

            pages = (total + page_size - 1) // page_size if total > 0 else 0

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": pages,
            }
    except Exception as e:
        logger.error(f"Failed to query request logs: {e}")
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}
