from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
import os
from dotenv import load_dotenv

from .models import Movement, Account, MovementCreate, AccountSummary
from .database import DynamoDBClient
from .auth import verify_api_key

load_dotenv()

app = FastAPI(
    title="Collaborative Funding API",
    description="API for managing financial movements in collaborative funding",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DynamoDB client
db_client = DynamoDBClient()

@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "collaborative-funding-api"}

@app.post("/api/movements", response_model=Movement)
async def create_movement(
    movement: MovementCreate,
    api_key: str = Depends(verify_api_key)
):
    """Create a new financial movement (Admin only)"""
    try:
        result = await db_client.create_movement(movement)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/movements/{account_id}")
async def get_movements(account_id: str):
    """Get all movements for a specific account"""
    try:
        movements = await db_client.get_movements_by_account(account_id)
        return {"account_id": account_id, "movements": movements}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/accounts/{account_id}", response_model=AccountSummary)
async def get_account_summary(account_id: str):
    """Get account summary including balance and status"""
    try:
        summary = await db_client.get_account_summary(account_id)
        if not summary:
            raise HTTPException(status_code=404, detail="Account not found")
        return summary
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/accounts/{account_id}/balance")
async def get_account_balance(account_id: str):
    """Get current balance for an account"""
    try:
        balance = await db_client.get_account_balance(account_id)
        return {"account_id": account_id, "balance": balance}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Handler for Vercel
handler = Mangum(app)