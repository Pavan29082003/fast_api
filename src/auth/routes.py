from fastapi import ( FastAPI, HTTPException, status, APIRouter,Body,BackgroundTasks,)
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta, timezone
from src.auth.core_logic import  send_verification_email
import os
import uuid
from src.auth import core_logic
from dotenv import load_dotenv
from passlib.hash import bcrypt
# from src.settings import settings
from boto3.dynamodb.conditions import Key, Attr
from src.database.connections import connections
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from src.auth.utils import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    store_refresh_token,
    get_refresh_token_from_db,
    delete_refresh_token,
    send_reset_verification_email,
     generate_password_reset_token,
    get_user_status_by_email,
    get_user_by_email,
    ALGORITHM,
    SECRET_KEY ,
    REFRESH_SECRET_KEY,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from .models import (RegisterRequest,PasswordChangeRequest,LoginData,
RefreshTokenData,PasswordResetData,EmailData,)


router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
users_table = connections.dynamodb.Table('UsersTable')
credentials_table = connections.dynamodb.Table('CredentialsTable')
roles_table = connections.dynamodb.Table('RolesTable')

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
        department=request.department
        hashed_password = bcrypt.hash(password)
        role = request.role
        user_status=request.user_status

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
                'organization_name': organization_name,
                'department':department,
                'user_status':user_status
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
        send_verification_email(email,password,user_id)
        reset_token = generate_password_reset_token(email, user_id) 

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                'status': 'success',
                'message': 'your account got hacked. A verification and password reset email has been sent to the admin.',
                'data': {'email': request.email,'reset_token':reset_token}
                
            }
        )
    

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


def verify_password(stored_password, provided_password):
    return bcrypt.verify(provided_password, stored_password)


@router.post("/change-password/{token}")
async def change_password(token: str, request: PasswordChangeRequest = Body(...),):
    try:
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("user_id")
            
            if user_id is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

       
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
    user = get_user_by_email(login_data.email)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not exist",
        )

    user_status = get_user_status_by_email(login_data.email)
    print(user_status)

    if user_status != 'active':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )
    authenticated_user = authenticate_user(login_data.email, login_data.password)
    if not authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": authenticated_user['email'], "user_id": authenticated_user['user_id']},
        expires_delta=access_token_expires
    )

    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_refresh_token(
        data={"sub": authenticated_user['email'], "user_id": authenticated_user['user_id']},
        expires_delta=refresh_token_expires
    )

    user_id = authenticated_user.get('user_id')

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID not found"
        )

    store_refresh_token(user_id, refresh_token)

    return {
        "user_id": user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "iat": datetime.utcnow().timestamp(),
        "exp": (datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()

    }
@router.post("/refresh")
async def refresh_access_token(refresh_token_data: RefreshTokenData):
    try:
        payload = jwt.decode(refresh_token_data.refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        
        user_id = payload.get("user_id")  

        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        stored_refresh_token = get_refresh_token_from_db(user_id)
        print("Stored Refresh Token:", stored_refresh_token)
        print("Provided Refresh Token:", refresh_token_data.refresh_token)
        
        if stored_refresh_token != refresh_token_data.refresh_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token does not match")

        new_access_token = create_access_token(data={"sub": payload.get("sub"), "user_id": user_id})  
        new_refresh_token = create_refresh_token(data={"sub": payload.get("sub"), "user_id": user_id}) 
        store_refresh_token(user_id, new_refresh_token)

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "iat": datetime.utcnow().timestamp(),
            "exp": (datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")


@router.post("/logout")
async def logout(user_id: str):
    result = delete_refresh_token(user_id)
    return result

@router.post("/forgot-password")
async def forgot_password(email_data: EmailData = Body(...),current_user: dict = Depends(get_current_user)):
    email = email_data.email
    user =  get_user_by_email(email) 
    user_id = user['user_id']
    
    reset_token = generate_password_reset_token(email, user_id) 
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    send_reset_verification_email(email, None,user['user_id'])
    
    return { "detail": "Password reset email sent if the email exists in our system", "reset_token":reset_token}


@router.post("/reset-password/{token}")
async def reset_password(token: str, password_data: PasswordResetData = Body(...),current_user: dict = Depends(get_current_user)):
    try:
    
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        user_id = payload.get("user_id")

        if email is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    new_password = password_data.new_password
    confirm_password = password_data.confirm_password
    
    if new_password != confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

    hashed_password = bcrypt.hash(new_password)

    credentials_table.update_item(
        Key={'user_id': user_id},
        UpdateExpression='SET password = :new_password',
        ExpressionAttributeValues={':new_password': hashed_password}
    )

    return {"detail": "Password has been reset successfully"}


        



