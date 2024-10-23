from fastapi import ( FastAPI, HTTPException, status, APIRouter,Body,BackgroundTasks,)
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta, timezone
import os
import uuid
from src.auth import core_logic
from dotenv import load_dotenv
from passlib.hash import bcrypt
from src.settings import settings
from boto3.dynamodb.conditions import Key, Attr
from src.database.connections import connections
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from src.auth.utils import (
    authenticate_user,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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

class LoginData(BaseModel):
    email: str
    password: str


def userexists(username: str, email: str):
    try:
        response = users_table.scan(
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
                'email'  : email,
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
                'message': 'your account got hacked. A verification and password reset email has been sent to the admin.',
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


@router.post("/login")
async def login_for_access_token(login_data: LoginData = Body(...)):
    user = authenticate_user(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user['email']}, expires_delta=access_token_expires
    )
    
    user_id = user.get('user_id')
    
    return {"access_token": access_token, "token_type": "bearer", "user_id": user_id}

@router.get("/protected")
async def protected_route(current_user: dict = Depends(get_current_user)):
    return {"message": "Access granted", "user": current_user}


        



