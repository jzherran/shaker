import json
import os
from urllib.parse import quote

from fastapi import Request
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from supabase import Client

from .auth import get_current_user_or_none
from .database import get_db as _get_db
from .i18n import register_jinja

# Synced from the browser when an admin enables "View as user" (see base.html).
VIEW_AS_USER_COOKIE = "shaker_view_as_user"

_templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=_templates_dir)
templates.env.filters["urlquote"] = lambda s: quote(str(s), safe="/")
templates.env.filters["next_q"] = lambda s: quote(str(s), safe="")
templates.env.filters["tojson"] = lambda v: Markup(json.dumps(v))


def _format_cop(value) -> str:
    """COP currency: $ 1.234,56 (dot thousands, comma decimals, 0-2 fraction digits)."""
    if value is None:
        return "$ 0"
    n = round(float(value), 2)
    int_part = int(n)
    frac_cents = round(abs(n - int_part) * 100)
    int_str = f"{abs(int_part):,}".replace(",", ".")
    if int_part < 0:
        int_str = "-" + int_str
    if frac_cents == 0:
        return f"$ {int_str}"
    if frac_cents % 10 == 0:
        return f"$ {int_str},{frac_cents // 10}"
    return f"$ {int_str},{frac_cents:02d}"


templates.env.filters["cop"] = _format_cop
register_jinja(templates)


def get_db() -> Client:
    return _get_db()


def admin_view_as_user(request: Request) -> bool:
    """True when an admin is browsing in member-style UI (cookie set by client)."""
    return request.cookies.get(VIEW_AS_USER_COOKIE) == "1"


async def get_template_context(request: Request) -> dict:
    """Build base template context with current user info."""
    user = await get_current_user_or_none(request)
    return {
        "request": request,
        "user": user,
        "is_admin": user.role == "admin" if user else False,
    }
