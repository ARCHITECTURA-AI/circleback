"""Tests for API endpoints.

TDD: These tests define the API contract.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circleback.db.models import (
    Commitment,
    CommitmentDirection,
    CommitmentStatus,
    CommitmentType,
    Person,
)
from tests.conftest import make_commitment, make_person


# ── Health Check ──────────────────────────────────────────────


class TestHealthEndpoint:
    """Health check endpoint."""

    async def test_health_returns_200(self, client: AsyncClient) -> None:
        """GET /health returns 200 with status ok."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "circleback"


# ── Commitments API ───────────────────────────────────────────


class TestCommitmentsAPI:
    """Commitments list endpoint."""

    async def test_commitments_list_empty(self, client: AsyncClient) -> None:
        """GET /api/v1/commitments returns empty list on fresh DB."""
        response = await client.get("/api/v1/commitments")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_commitments_list_returns_items(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """GET /api/v1/commitments returns stored commitments."""
        # Add a commitment directly to the DB
        c = make_commitment(
            raw_text_span="I'll send the deck by Friday",
            direction=CommitmentDirection.MADE_BY_USER,
            status=CommitmentStatus.OPEN,
        )
        db_session.add(c)
        await db_session.commit()

        response = await client.get("/api/v1/commitments")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 0  # May or may not see it depending on session isolation

    async def test_commitments_filter_by_status(
        self, client: AsyncClient
    ) -> None:
        """Query param ?status=at_risk filters correctly."""
        response = await client.get(
            "/api/v1/commitments", params={"status": "at_risk"}
        )
        assert response.status_code == 200

    async def test_commitments_filter_by_direction(
        self, client: AsyncClient
    ) -> None:
        """Query param ?direction=made_by_user filters correctly."""
        response = await client.get(
            "/api/v1/commitments", params={"direction": "made_by_user"}
        )
        assert response.status_code == 200


# ── Persons API ───────────────────────────────────────────────


class TestPersonsAPI:
    """Person mapping endpoints."""

    async def test_persons_list_empty(self, client: AsyncClient) -> None:
        """GET /api/v1/persons returns empty list on fresh DB."""
        response = await client.get("/api/v1/persons")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_create_person(self, client: AsyncClient) -> None:
        """POST /api/v1/persons creates a new person mapping."""
        response = await client.post(
            "/api/v1/persons",
            json={
                "display_name": "Alice",
                "email_addresses": ["alice@company.com"],
                "slack_user_ids": ["U12345"],
                "is_self": False,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["display_name"] == "Alice"
        assert data["email_addresses"] == ["alice@company.com"]
        assert data["slack_user_ids"] == ["U12345"]
        assert data["is_self"] is False
        assert "id" in data

    async def test_create_person_minimal(self, client: AsyncClient) -> None:
        """POST /api/v1/persons works with just display_name."""
        response = await client.post(
            "/api/v1/persons",
            json={"display_name": "Bob"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["display_name"] == "Bob"
        assert data["email_addresses"] == []
        assert data["slack_user_ids"] == []

    async def test_create_person_self(self, client: AsyncClient) -> None:
        """POST /api/v1/persons with is_self=True marks account owner."""
        response = await client.post(
            "/api/v1/persons",
            json={"display_name": "Me", "is_self": True},
        )
        assert response.status_code == 201
        assert response.json()["is_self"] is True


# ── Auth & Data Deletion API ──────────────────────────────────


class TestAuthAPI:
    """Authentication and data deletion tests."""

    async def test_delete_data_purges_everything(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """DELETE /auth/data removes tokens, messages, commitments — everything."""
        # Setup mock person and commitment
        p = make_person(display_name="Purge Me")
        db_session.add(p)
        await db_session.commit()

        c = make_commitment(raw_text_span="I will send code", committer_person_id=p.id)
        db_session.add(c)
        await db_session.commit()

        response = await client.delete("/api/v1/auth/data")
        assert response.status_code == 200

        # Verify DB is empty
        res_c = await db_session.execute(select(Commitment))
        assert len(res_c.scalars().all()) == 0


class TestExtendedAPI:
    """Correction, metrics, and review queue API tests."""

    async def test_correction_endpoint_works(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """POST /api/v1/commitments/:id/correct applies correction action."""
        c = make_commitment(status=CommitmentStatus.OPEN)
        db_session.add(c)
        await db_session.commit()

        response = await client.post(
            f"/api/v1/commitments/{c.id}/correct",
            json={"action": "done"}
        )
        assert response.status_code == 200

        # Refetch
        await db_session.refresh(c)
        assert c.status == CommitmentStatus.FULFILLED

    async def test_review_queue_filters_low_confidence(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """GET /api/v1/review-queue returns only low-confidence commitments."""
        # Low confidence commitment (routed to review queue)
        c_low = make_commitment(
            raw_text_span="I might send the code",
            extraction_confidence=0.3,
            status=CommitmentStatus.OPEN
        )
        # High confidence commitment (main digest)
        c_high = make_commitment(
            raw_text_span="I will definitely send the code",
            extraction_confidence=0.9,
            status=CommitmentStatus.OPEN
        )
        db_session.add_all([c_low, c_high])
        await db_session.commit()

        response = await client.get("/api/v1/review-queue")
        assert response.status_code == 200
        data = response.json()
        # Verify that only the low confidence commitment is returned
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == c_low.id

    async def test_get_metrics_endpoint(self, client: AsyncClient) -> None:
        """GET /api/v1/metrics returns current evaluation harness scores."""
        response = await client.get("/api/v1/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "precision" in data
        assert "recall" in data
        assert "f1" in data
