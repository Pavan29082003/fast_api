from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from passlib.hash import bcrypt
from src.settings import settings
from src.database.connections import connections
import uuid
from boto3.dynamodb.conditions import Key, Attr



load_dotenv()
router=APIRouter()
users_table = connections.dynamodb.Table('UsersTable')
credentials_table = connections.dynamodb.Table('CredentialsTable')
roles_table = connections.dynamodb.Table('RolesTable')

class UserCreationRequest(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: str
    phone_number: str
    password: str
    role: str
    organization_name: str


def userexists(username: str, email: str):
    try:
        response = users_table.scan(
            FilterExpression=Attr('username').eq(username) | Attr('email').eq(email)
        )
        return len(response['Items']) > 0
    except ClientError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error querying database")


def get_user_role(user_id: str):
    response = roles_table.get_item(Key={'user_id': user_id})
    if 'Item' not in response:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
    return response['Item']['role']

def has_permission_to_create(current_role: str, new_role: str):
    if current_role == 'Super Admin' and new_role in ['Admin', 'User']:
        return True
    elif current_role == 'Admin' and new_role == 'User':
        return True
    else:
        return False


@router.post("/create-user/{creator_id}")
async def create_user(creator_id: str, request: UserCreationRequest):
    try:
        creator_role = get_user_role(creator_id)

        if not has_permission_to_create(creator_role, request.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{creator_role}s are not allowed to create {request.role}s."
            )

        user_id = str(uuid.uuid4())
        first_name = request.first_name
        last_name = request.last_name
        username = request.username
        email = request.email
        phone_number = request.phone_number
        password = request.password
        hashed_password = bcrypt.hash(password)
        organization_name = request.organization_name
        role = request.role

        if userexists(username, email):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={'msg': "User already exists with the same username or email"}
            )

        users_table.put_item(
            Item={
                'user_id': user_id,
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'email': email,
                'phone_number': phone_number,
                'organization_name': organization_name
            }
        )

        credentials_table.put_item(
            Item={
                'user_id': user_id,
                'email'  :email,
                'password': hashed_password
            }
        )

        roles_table.put_item(
            Item={
                'user_id': user_id,
                'role': role
            }
        )

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                'status': 'success',
                'message': f'{role} created successfully.',
                'data': {'email': request.email}
            }
        )

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
