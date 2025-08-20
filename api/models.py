from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal
from enum import Enum

class MovementType(str, Enum):
    CONTRIBUTION = "contribution"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    FEE = "fee"

class MovementStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MovementCreate(BaseModel):
    account_id: str = Field(..., description="Account identifier")
    amount: float = Field(..., gt=0, description="Movement amount")
    movement_type: MovementType
    description: str = Field(..., max_length=500)
    reference: Optional[str] = Field(None, description="External reference")
    metadata: Optional[dict] = Field(default_factory=dict)

class Movement(BaseModel):
    movement_id: str
    account_id: str
    amount: float
    movement_type: MovementType
    status: MovementStatus
    description: str
    reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: str
    metadata: Optional[dict] = None

class Account(BaseModel):
    account_id: str
    owner_name: str
    email: str
    created_at: datetime
    status: Literal["active", "inactive", "suspended"]
    metadata: Optional[dict] = None

class AccountSummary(BaseModel):
    account_id: str
    owner_name: str
    email: str
    balance: float
    total_contributions: float
    total_withdrawals: float
    movement_count: int
    status: Literal["active", "inactive", "suspended"]
    created_at: datetime
    last_movement_at: Optional[datetime] = None