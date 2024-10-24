import boto3
from botocore.exceptions import ClientError
from passlib.hash import bcrypt
from passlib.context import CryptContext
from fastapi import (HTTPException, status,Depends, HTTPException,)
from fastapi.security import OAuth2PasswordBearer
from src.database.connections import connections
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from boto3.dynamodb.conditions import Key,Attr
import string  
import random


users_table = connections.dynamodb.Table('UsersTable')
credentials_table = connections.dynamodb.Table('CredentialsTable')
roles_table=connections.dynamodb.Table("RolesTable")

def userexists(username: str, email: str) -> bool:
    try:
        response = users_table.scan(
            FilterExpression=Attr('username').eq(username) | Attr('email').eq(email)
        )

        if len(response['Items']) > 0:
            return True  
        return False

    except ClientError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error querying database")

def get_user_role(user_id: str):
    response = roles_table.get_item(Key={'user_id': user_id})
    if 'Item' not in response:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
    return response['Item']['role']

def get_users_by_organization(organization_name: str):
    # Query the users table to get all users that match the given organization name
    response = users_table.scan(
        FilterExpression=Attr('organization_name').eq(organization_name)
    )

    if 'Items' not in response or not response['Items']:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No users found for this organization")

    return response['Items']


def has_permission_to_create(current_role: str, new_role: str):
    if current_role == 'Super Admin' and new_role in ['Admin', 'User']:
        return True
    elif current_role == 'Admin' and new_role == 'User':
        return True
    else:
        return False

def has_permission_to_get_users(current_role: str, requested_role: str):
    if current_role == 'Super Admin':
        return True  
    elif current_role == 'Admin' and requested_role == 'User':
        return True  
    return False

async def get_user_by_id(user_id: str):
    try:
       
        response = users_table.query(
            KeyConditionExpression=Key('user_id').eq(user_id)  
        )
        if 'Items' not in response or not response['Items']:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return response['Items'][0]  

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user profile: {str(e)}"
        )
    
async def get_users_by_role(role: str):
    try:
        print(f"Filtering users with role: {role}")  
        response = roles_table.scan(
            FilterExpression=Attr('role').eq(role)
        )
        print("Scan response:", response) 

        if 'Items' not in response or not response['Items']:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No users found with the specified role"
            )

        return response['Items']

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving users: {str(e)}"
        )
async def get_user_details(user_id: str):
   
    response = users_table.query(
        KeyConditionExpression=Key('user_id').eq(user_id)
    )
    
    
    if response.get('Items'):
        
        return {
            "email": response['Items'][0].get("email"),  
            "user_status": response['Items'][0].get("user_status")          }
    
    return {}  
def generate_random_password() -> str:
        return str(random.randint(100000, 999999)) 