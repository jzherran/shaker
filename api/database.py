import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime
import uuid
import os
from typing import List, Optional
from decimal import Decimal

from .models import Movement, MovementCreate, AccountSummary, MovementType, MovementStatus

class DynamoDBClient:
    def __init__(self):
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        self.movements_table = self.dynamodb.Table(os.getenv('DYNAMODB_TABLE_MOVEMENTS', 'financial_movements'))
        self.accounts_table = self.dynamodb.Table(os.getenv('DYNAMODB_TABLE_ACCOUNTS', 'accounts'))

    def _decimal_to_float(self, obj):
        """Convert Decimal objects to float for JSON serialization"""
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._decimal_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._decimal_to_float(i) for i in obj]
        return obj

    async def create_movement(self, movement_data: MovementCreate) -> Movement:
        """Create a new financial movement"""
        movement_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        item = {
            'movement_id': movement_id,
            'account_id': movement_data.account_id,
            'amount': Decimal(str(movement_data.amount)),
            'movement_type': movement_data.movement_type.value,
            'status': MovementStatus.COMPLETED.value,
            'description': movement_data.description,
            'reference': movement_data.reference,
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'created_by': 'admin',  # In a real app, this would come from auth
            'metadata': movement_data.metadata or {}
        }
        
        self.movements_table.put_item(Item=item)
        
        # Update account balance
        await self._update_account_balance(movement_data.account_id, movement_data.amount, movement_data.movement_type)
        
        return Movement(
            movement_id=movement_id,
            account_id=movement_data.account_id,
            amount=movement_data.amount,
            movement_type=movement_data.movement_type,
            status=MovementStatus.COMPLETED,
            description=movement_data.description,
            reference=movement_data.reference,
            created_at=now,
            updated_at=now,
            created_by='admin',
            metadata=movement_data.metadata
        )

    async def get_movements_by_account(self, account_id: str) -> List[dict]:
        """Get all movements for a specific account"""
        response = self.movements_table.query(
            IndexName='account-index',  # You'll need to create this GSI
            KeyConditionExpression=Key('account_id').eq(account_id),
            ScanIndexForward=False  # Most recent first
        )
        
        movements = []
        for item in response.get('Items', []):
            movements.append(self._decimal_to_float(item))
        
        return movements

    async def get_account_balance(self, account_id: str) -> float:
        """Calculate current balance for an account"""
        movements = await self.get_movements_by_account(account_id)
        balance = 0.0
        
        for movement in movements:
            amount = float(movement['amount'])
            movement_type = movement['movement_type']
            
            if movement_type == MovementType.CONTRIBUTION.value:
                balance += amount
            elif movement_type in [MovementType.WITHDRAWAL.value, MovementType.FEE.value]:
                balance -= amount
            # Transfer logic would depend on whether it's incoming or outgoing
        
        return balance

    async def get_account_summary(self, account_id: str) -> Optional[AccountSummary]:
        """Get comprehensive account summary"""
        # Get account info (assuming it exists in accounts table)
        try:
            response = self.accounts_table.get_item(Key={'account_id': account_id})
            account = response.get('Item')
            
            if not account:
                # Create a default account for demo purposes
                account = {
                    'account_id': account_id,
                    'owner_name': f'User {account_id}',
                    'email': f'user{account_id}@example.com',
                    'status': 'active',
                    'created_at': datetime.utcnow().isoformat()
                }
            
            # Get movements and calculate summary
            movements = await self.get_movements_by_account(account_id)
            
            total_contributions = sum(
                float(m['amount']) for m in movements 
                if m['movement_type'] == MovementType.CONTRIBUTION.value
            )
            total_withdrawals = sum(
                float(m['amount']) for m in movements 
                if m['movement_type'] == MovementType.WITHDRAWAL.value
            )
            
            balance = await self.get_account_balance(account_id)
            
            last_movement_at = None
            if movements:
                last_movement_at = datetime.fromisoformat(movements[0]['created_at'])
            
            return AccountSummary(
                account_id=account_id,
                owner_name=account['owner_name'],
                email=account['email'],
                balance=balance,
                total_contributions=total_contributions,
                total_withdrawals=total_withdrawals,
                movement_count=len(movements),
                status=account['status'],
                created_at=datetime.fromisoformat(account['created_at']),
                last_movement_at=last_movement_at
            )
            
        except Exception as e:
            print(f"Error getting account summary: {e}")
            return None

    async def _update_account_balance(self, account_id: str, amount: float, movement_type: MovementType):
        """Update account balance after a movement"""
        # In a real implementation, you might want to maintain a balance field
        # in the accounts table for performance
        pass