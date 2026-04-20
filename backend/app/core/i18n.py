"""
gettext-backed translations for PDFs, emails and audit exports.

Catalog: ``backend/locale/{es,en}/LC_MESSAGES/messages.{po,mo}``.
"""

from __future__ import annotations

import gettext
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

_LOCALE_ROOT = Path(__file__).resolve().parents[2] / "locale"


def normalize_lang(code: str | None) -> str:
    if not code or not str(code).strip():
        return "es"
    s = str(code).strip().lower().replace("_", "-")
    if s.startswith("en"):
        return "en"
    return "es"


@lru_cache(maxsize=8)
def _translation_for(lang: str) -> gettext.NullTranslations:
    """
    English (``en``) uses ``NullTranslations``: msgids are already English.
    Spanish loads ``locale/es/LC_MESSAGES/messages.mo``.
    """
    lng = normalize_lang(lang)
    if lng == "en":
        return gettext.NullTranslations()
    try:
        return gettext.translation(
            "messages",
            localedir=str(_LOCALE_ROOT),
            languages=["es"],
            fallback=False,
        )
    except OSError:
        return gettext.NullTranslations()


def get_translator(lang: str | None) -> Callable[[str], str]:
    """Return ``gettext`` for the given language (default Spanish)."""
    return _translation_for(normalize_lang(lang)).gettext


def clear_translation_cache() -> None:
    """Test hook after regenerating ``.mo`` files."""
    _translation_for.cache_clear()
