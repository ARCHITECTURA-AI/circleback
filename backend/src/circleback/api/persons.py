"""Persons API endpoints — manual identity mapping.

In v1, cross-channel identity resolution is manual: the user
maintains a mapping of email addresses and Slack user IDs to
Person records. This API powers that workflow.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circleback.db import get_db
from circleback.db.models import Person
from circleback.api.session import get_current_user

router = APIRouter(tags=["persons"])


# ── Request/Response schemas ──────────────────────────────────


class PersonCreate(BaseModel):
    """Schema for creating a new person mapping."""

    display_name: str
    email_addresses: list[str] = []
    slack_user_ids: list[str] = []
    is_self: bool = False


class PersonResponse(BaseModel):
    """Serialized person for API responses."""

    id: str
    display_name: str
    email_addresses: list[str]
    slack_user_ids: list[str]
    is_self: bool

    model_config = {"from_attributes": True}


class PersonListResponse(BaseModel):
    """List of person mappings."""

    items: list[PersonResponse]
    total: int


# ── Endpoints ─────────────────────────────────────────────────


@router.get("/persons", response_model=PersonListResponse)
async def list_persons(
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> PersonListResponse:
    """List all person mappings."""
    result = await db.execute(select(Person))
    persons = result.scalars().all()

    items = [
        PersonResponse(
            id=p.id,
            display_name=p.display_name,
            email_addresses=p.email_addresses,
            slack_user_ids=p.slack_user_ids,
            is_self=p.is_self,
        )
        for p in persons
    ]

    return PersonListResponse(items=items, total=len(items))


@router.post("/persons", response_model=PersonResponse, status_code=201)
async def create_person(
    body: PersonCreate,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> PersonResponse:
    """Create a new person mapping."""
    person = Person(
        display_name=body.display_name,
        email_addresses=body.email_addresses,
        slack_user_ids=body.slack_user_ids,
        is_self=body.is_self,
    )
    db.add(person)
    await db.flush()

    return PersonResponse(
        id=person.id,
        display_name=person.display_name,
        email_addresses=person.email_addresses,
        slack_user_ids=person.slack_user_ids,
        is_self=person.is_self,
    )
