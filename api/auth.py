from fastapi import Request, HTTPException, status
from jose import jwt, JWTError
from .config import get_settings
from .database import get_db
from .models.user import User
from typing import Optional


async def get_current_user_or_none(request: Request) -> Optional[User]:
    """Extract user from session cookie. Returns None if not authenticated."""
    token = request.cookies.get("session")
    if not token:
        return None

    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=["HS256"]
        )
        auth_id = payload.get("sub")
        if not auth_id:
            return None
    except JWTError:
        return None

    db = get_db()
    result = db.table("users").select("*").eq("auth_id", auth_id).execute()
    if not result.data:
        return None

    return User(**result.data[0])


async def get_current_user(request: Request) -> User:
    """Require authenticated user. Raises 401 if not authenticated."""
    user = await get_current_user_or_none(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


async def require_admin(request: Request) -> User:
    """Require authenticated admin user. Raises 403 if not admin."""
    user = await get_current_user(request)
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def create_session_token(auth_id: str, email: str) -> str:
    """Create a signed JWT session token."""
    settings = get_settings()
    return jwt.encode(
        {"sub": auth_id, "email": email},
        settings.secret_key,
        algorithm="HS256",
    )
