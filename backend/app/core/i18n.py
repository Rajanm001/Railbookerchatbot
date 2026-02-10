"""
Internationalization (i18n) support for Railbookers Rail Vacation Planner.
Provides translations for all 10 supported languages.
Delegates to app.services.translations for the canonical translation store.
"""

from typing import Dict, Any, Optional
from enum import Enum


class Language(str, Enum):
    """Supported languages."""
    EN = "en"
    FR = "fr"
    ES = "es"
    DE = "de"
    IT = "it"
    HI = "hi"
    JA = "ja"
    ZH = "zh"
    PT = "pt"
    AR = "ar"


# Supported language codes set
SUPPORTED_LANGS = {lang.value for lang in Language}


def get_translation(key: str, lang: str = "en", **kwargs) -> str:
    """Get translated string for a key in specified language."""
    lang = lang.lower()
    if lang not in SUPPORTED_LANGS:
        lang = "en"
    # Delegate to translations module for chat-flow keys
    try:
        from app.services.translations import t
        result = t(key, lang)
        if result != key:
            if kwargs:
                try:
                    result = result.format(**kwargs)
                except (KeyError, IndexError):
                    pass
            return result
    except ImportError:
        pass
    return key


def get_all_translations(lang: str = "en") -> Dict[str, str]:
    """Get all translations for a language."""
    lang = lang.lower()
    if lang not in SUPPORTED_LANGS:
        lang = "en"
    try:
        from app.services.translations import _TRANSLATIONS
        result = {}
        for key, lang_dict in _TRANSLATIONS.items():
            if isinstance(lang_dict, dict):
                val = lang_dict.get(lang, lang_dict.get("en", ""))
                if isinstance(val, (list, tuple)):
                    result[key] = ", ".join(str(v) for v in val)
                else:
                    result[key] = str(val)
        return result
    except (ImportError, AttributeError):
        return {}


def get_supported_languages() -> list:
    """Get list of supported languages with metadata."""
    return [
        {"code": "en", "name": "English", "native_name": "English"},
        {"code": "fr", "name": "French", "native_name": "Français"},
        {"code": "es", "name": "Spanish", "native_name": "Español"},
        {"code": "de", "name": "German", "native_name": "Deutsch"},
        {"code": "it", "name": "Italian", "native_name": "Italiano"},
        {"code": "hi", "name": "Hindi", "native_name": "हिन्दी"},
        {"code": "ja", "name": "Japanese", "native_name": "日本語"},
        {"code": "zh", "name": "Chinese", "native_name": "中文"},
        {"code": "pt", "name": "Portuguese", "native_name": "Português"},
        {"code": "ar", "name": "Arabic", "native_name": "العربية"},
    ]


def translate_dict(data: Dict[str, Any], lang: str = "en") -> Dict[str, Any]:
    """Translate all translatable fields in a dictionary."""
    translated = {}
    for key, value in data.items():
        if isinstance(value, str):
            tr = get_translation(value, lang)
            translated[key] = tr if tr != value else value
        elif isinstance(value, dict):
            translated[key] = translate_dict(value, lang)
        elif isinstance(value, list):
            translated[key] = [
                translate_dict(item, lang) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            translated[key] = value
    return translated
