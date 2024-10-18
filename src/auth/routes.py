from fastapi import FastAPI, HTTPException, status, APIRouter
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError
from fastapi.responses import JSONResponse
import os
import uuid
from src.auth import core_logic
from dotenv import load_dotenv
from passlib.hash import bcrypt
from src.settings import settings
from boto3.dynamodb.conditions import Key, Attr
from src.database.connections import connections

load_dotenv()

router = APIRouter()


users_table = connections.dynamodb.Table('UsersTable')
credentials_table = connections.dynamodb.Table('CredentialsTable')
roles_table = connections.dynamodb.Table('RolesTable')

class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: str
    phone_number: str
    password: str
    role: str
    organization_name: str

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


def userexists(username: str, email: str):
    try:
        response = credentials_table.scan(
            FilterExpression=Attr('username').eq(username) | Attr('email').eq(email)
        )
        return len(response['Items']) > 0
    except ClientError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error querying database")

@router.post("/register")
async def register(request: RegisterRequest):
    try:
        user_id = str(uuid.uuid4())
        first_name = request.first_name
        last_name = request.last_name
        phone_number = request.phone_number
        organization_name = request.organization_name
        username = request.username
        email = request.email
        password = request.password
        hashed_password = bcrypt.hash(password)
        role = request.role

        if userexists(username, email):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={'msg': "User already exists with the same username or email"}
            )
        core_logic.send_verification_email(email, password, user_id)

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
                'message': 'Super Admin created successfully. A verification and password reset email has been sent to the admin.',
                'data': {'email': request.email}
            }
        )

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


def verify_password(stored_password, provided_password):
    return bcrypt.verify(provided_password, stored_password)


@router.post("/change-password/{user_id}")
async def change_password(user_id: str, request: PasswordChangeRequest):
    try:
        current_password = request.current_password
        new_password = request.new_password
        confirm_password = request.confirm_password

        if not current_password or not new_password or not confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Current password, new password, and confirm password are required."
            )
    
        if new_password != confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="New password and confirm password do not match."
            )

        response = credentials_table.get_item(
            Key={'user_id': user_id}
        )

        if 'Item' not in response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found."
            )

        stored_password_hash = response['Item']['password']

        if not verify_password(stored_password_hash, current_password):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Current password is incorrect."
            )

        new_password_hash = bcrypt.hash(new_password)

        credentials_table.update_item(
            Key={'user_id': user_id},
            UpdateExpression="SET password = :p",
            ExpressionAttributeValues={':p': new_password_hash},
            ReturnValues="UPDATED_NEW"
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'status': 'success', 'message': 'Password updated successfully.'}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=str(e)
        )





        



