"""Alembic environment restricted to the local RAG integration database."""

from __future__ import annotations

import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _local_database_url() -> str:
    raw_url = os.environ.get("RAG_DATABASE_URL", "").strip()
    if not raw_url:
        raise ValueError("RAG_DATABASE_URL is required for local RAG migrations")
    try:
        url = make_url(raw_url)
    except Exception:
        raise ValueError("RAG_DATABASE_URL is invalid") from None

    database_name = os.environ.get("RAG_LOCAL_DATABASE_NAME", "starter_rag_integration").strip()
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database_name) is None:
        raise ValueError("RAG_LOCAL_DATABASE_NAME is invalid")
    socket_host = url.query.get("host")
    local_host = url.host in {None, "localhost", "127.0.0.1", "::1"}
    local_socket = isinstance(socket_host, str) and socket_host.startswith("/")
    if (
        url.drivername != "postgresql+asyncpg"
        or url.database != database_name
        or not (local_host or local_socket)
    ):
        raise ValueError("RAG_DATABASE_URL must target the local RAG integration database")
    return url.render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    context.configure(
        url=_local_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _local_database_url()
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    def do_run_migrations(sync_connection) -> None:
        context.configure(
            connection=sync_connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    async def run_async_migrations() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
