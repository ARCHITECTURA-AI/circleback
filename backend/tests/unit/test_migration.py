"""Unit tests for migration model consistency.

Validates that all ORM models are self-consistent and can be created
via Base.metadata.create_all without errors — catching FK references
to missing tables, column type mismatches, etc.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from circleback.db.models import Base


@pytest.mark.asyncio
async def test_create_all_succeeds():
    """Base.metadata.create_all should succeed with all models defined."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Verify key tables exist
    async with engine.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )

    expected_tables = {
        "users", "persons", "threads", "messages", "commitments",
        "commitment_events", "eval_labels", "oauth_tokens", "unrecognized_senders",
    }
    assert expected_tables.issubset(set(table_names)), (
        f"Missing tables: {expected_tables - set(table_names)}"
    )

    await engine.dispose()


@pytest.mark.asyncio
async def test_user_model_columns():
    """User model should have the expected columns."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("users")}
        )

    assert "id" in columns
    assert "email" in columns
    assert "display_name" in columns
    assert "created_at" in columns

    await engine.dispose()


@pytest.mark.asyncio
async def test_user_id_fk_on_all_tenant_tables():
    """All tenant-scoped tables should have a user_id column."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tenant_tables = [
        "persons", "threads", "messages", "commitments",
        "eval_labels", "oauth_tokens", "unrecognized_senders",
    ]

    async with engine.connect() as conn:
        for table_name in tenant_tables:
            columns = await conn.run_sync(
                lambda sync_conn, tn=table_name: {
                    c["name"] for c in inspect(sync_conn).get_columns(tn)
                }
            )
            assert "user_id" in columns, f"Table {table_name} is missing user_id column"

    await engine.dispose()


@pytest.mark.asyncio
async def test_messages_has_sender_handle():
    """Messages table should have a sender_handle column."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("messages")}
        )

    assert "sender_handle" in columns

    await engine.dispose()
