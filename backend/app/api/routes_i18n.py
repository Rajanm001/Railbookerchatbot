"""
Internationalization (i18n) API routes.
Provides translations and language support for the chatbot.
Supports all 10 languages: en, fr, es, de, it, hi, ja, zh, pt, ar.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, List

from app.core.i18n import (
    get_translation,
    get_all_translations,
    get_supported_languages,
    SUPPORTED_LANGS,
)

router = APIRouter(tags=["i18n"], prefix="/i18n")


@router.get("/languages", response_model=List[Dict[str, str]])
def list_supported_languages():
    """
    Get list of supported languages with metadata.

    Returns:
        [
            {"code": "en", "name": "English", "native_name": "English"},
            ...
        ]
    """
    return get_supported_languages()


@router.get("/translations/{lang}", response_model=Dict[str, str])
def get_translations(
    lang: str = "en"
):
    """
    Get all translations for a specific language.

    Args:
        lang: Language code (en, fr, es, de, it, hi, ja, zh, pt, ar)

    Returns:
        Dictionary of all translation keys and values
    """
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {lang}. Supported: {', '.join(sorted(SUPPORTED_LANGS))}"
        )

    return get_all_translations(lang)


@router.get("/translate")
def translate_key(
    key: str = Query(..., description="Translation key"),
    lang: str = Query("en", description="Language code")
):
    """
    Translate a single key to specified language.

    Args:
        key: Translation key (e.g., "welcome")
        lang: Language code (en, fr, es, de, it, hi, ja, zh, pt, ar)

    Returns:
        {"key": "welcome", "translation": "Translated text", "lang": "fr"}
    """
    if lang not in SUPPORTED_LANGS:
        lang = "en"

    translation = get_translation(key, lang)

    return {
        "key": key,
        "translation": translation,
        "lang": lang
    }
