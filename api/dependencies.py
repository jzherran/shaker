from fastapi import Request
from fastapi.templating import Jinja2Templates
from supabase import Client
from .database import get_db as _get_db
from .auth import get_current_user_or_none
from .models.user import User
from typing import Optional
import os

_templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=_templates_dir)


def get_db() -> Client:
    return _get_db()


async def get_template_context(request: Request) -> dict:
    """Build base template context with current user info."""
    user = await get_current_user_or_none(request)
    return {
        "request": request,
        "user": user,
        "is_admin": user.role == "admin" if user else False,
    }
