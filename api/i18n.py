"""Lightweight i18n: JSON locales + Jinja helper."""

from __future__ import annotations

import json
import os
from typing import Any

from jinja2 import pass_context
from starlette.requests import Request

_LOCALES: dict[str, dict[str, Any]] = {}
_DIR = os.path.join(os.path.dirname(__file__), "locales")


def _load_locales() -> None:
    global _LOCALES
    if _LOCALES:
        return
    for name in ("en", "es"):
        path = os.path.join(_DIR, f"{name}.json")
        with open(path, encoding="utf-8") as f:
            _LOCALES[name] = json.load(f)


def _get_nested(data: dict[str, Any], key: str) -> Any:
    cur: Any = data
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def locale_from_request(request: Request | None) -> str:
    if request is None:
        return "en"
    lang = getattr(request.state, "locale", None) or request.cookies.get("lang", "en")
    if lang not in ("en", "es"):
        lang = "en"
    return lang


def translate(lang: str, key: str, **kwargs: Any) -> str:
    _load_locales()
    for lg in (lang, "en"):
        if lg not in _LOCALES:
            continue
        val = _get_nested(_LOCALES[lg], key)
        if val is None:
            continue
        if not isinstance(val, str):
            return key
        if kwargs:
            try:
                return val.format(**kwargs)
            except (KeyError, ValueError):
                return val
        return val
    return key


@pass_context
def t_filter(context: dict[str, Any], key: str, **kwargs: Any) -> str:
    request = context.get("request")
    lang = locale_from_request(request)
    return translate(lang, key, **kwargs)


def register_jinja(templates: Any) -> None:
    templates.env.globals["t"] = t_filter


def translate_html(request: Request | None, key: str, **kwargs: Any) -> str:
    return translate(locale_from_request(request), key, **kwargs)
