from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatSessionCreateIn(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ChatSessionOut(BaseModel):
    id: UUID
    empresa_id: UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatMessageOut(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    model: str | None = None
    created_at: datetime
