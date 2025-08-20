"""
Script to create DynamoDB tables for the application
Run this once to set up your AWS infrastructure
"""

import boto3
import os
from dotenv import load_dotenv

load_dotenv()

def create_tables():
    dynamodb = boto3.client(
        'dynamodb',
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )
    
    # Create movements table
    try:
        dynamodb.create_table(
            TableName=os.getenv('DYNAMODB_TABLE_MOVEMENTS', 'financial_movements'),
            KeySchema=[
                {
                    'AttributeName': 'movement_id',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'movement_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'account_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'created_at',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'account-index',
                    'KeySchema': [
                        {
                            'AttributeName': 'account_id',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'created_at',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'BillingMode': 'PAY_PER_REQUEST'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print("Created financial_movements table")
    except dynamodb.exceptions.ResourceInUseException:
        print("financial_movements table already exists")
    
    # Create accounts table
    try:
        dynamodb.create_table(
            TableName=os.getenv('DYNAMODB_TABLE_ACCOUNTS', 'accounts'),
            KeySchema=[
                {
                    'AttributeName': 'account_id',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'account_id',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print("Created accounts table")
    except dynamodb.exceptions.ResourceInUseException:
        print("accounts table already exists")

if __name__ == "__main__":
    create_tables()