from fastapi import HTTPException, Header
from typing import Optional
import os

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key for admin endpoints"""
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required for this endpoint"
        )
    
    expected_key = os.getenv("API_KEY")
    if not expected_key or x_api_key != expected_key:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    
    return x_api_key