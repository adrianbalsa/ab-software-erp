"""Compat: el webhook canónico vive en ``app.api.v1.webhooks.stripe``."""

from __future__ import annotations

from app.api.v1.webhooks.stripe import router

__all__ = ["router"]
