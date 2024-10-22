import logging 
from datetime import datetime, timedelta, timezone
import jwt
import boto3
from botocore.exceptions import ClientError
from passlib.hash import bcrypt
from passlib.context import CryptContext
from fastapi import (HTTPException, status,Depends, HTTPException,)
from fastapi.security import OAuth2PasswordBearer
from src.auth.core_logic import  send_verification_email
from src.database.connections import connections
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from boto3.dynamodb.conditions import Key, Attr
import base64
import os 
import pickle


logging.basicConfig(level=logging.INFO)
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

SECRET_KEY = "6fee615b2e2938c237f9cf7d49f7b55afb78ac626dd6c983f4cc125aecf22b070325b6eb9554893fc787f0d7154225bf02f324d244d7c9ce0a205cca82fcc02b8382ac8cd1c6126d43315a3da96d564951d72d0f3291f78bb2b9d9e372ed499fbf78f421c0dc0487642f94e08e545d1f1dc00423699cc66623981c8c902fe2a103d8825ab4bc03f7d8658eca8bc4f24c97bbc33277d7571f6bcfdd40c872e70054caf8a263fdbcb741932596d62fc85e68cbfa5eb9c8c237c09455bf8d5dcc34e2acfd584c8f0f785c7c9d1f23b9cab8cd78d5bcfa1f385556ba66fd26469dce8908414579bbe2cabc599ce9c5a1e58734333acc303572c1750a90f6e779c151"
ALGORITHM = "HS256"
REFRESH_SECRET_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJSb2xlIjoiQWRtaW4iLCJJc3N1ZXIiOiJJc3N1ZXIiLCJVc2VybmFtZSI6IkphdmFJblVzZSIsImV4cCI6MTcyOTQ4NDU4OCwiaWF0IjoxNzI5NDg0NTg4fQ.euVG7j35fsPxEhO1NJFuoNzU283fy4opLRXXN51TvT4"
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 10
ACCESS_TOKEN_EXPIRE_MINUTES = 100
REFRESH_TOKEN_EXPIRE_DAYS = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
users_table = connections.dynamodb.Table('UsersTable')
credentials_table = connections.dynamodb.Table('CredentialsTable')

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc) 
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def refresh_access_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        
        user_id = payload.get("user_id") 
        email = payload.get("sub")
        
        if email is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        
        new_access_token = create_access_token(data={"sub": email, "user_id": user_id})

        return {
            "access_token": new_access_token,
            "iat": datetime.now(timezone.utc).timestamp(),  
            "exp": (datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp() 
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
    
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

def create_refresh_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta if expires_delta else timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc)  
    })
    encoded_jwt = jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(provided_password, stored_password):
    return pwd_context.verify(provided_password, stored_password)

def get_user_by_email(email: str):
    try:
    
        response = credentials_table.scan(
            FilterExpression=Attr('email').eq(email)
        )
        
        items = response.get('Items', [])
        
        return items[0] if items else None
    
    except Exception as e:
        print(f"Error fetching user by email: {str(e)}")
        return None

def get_user_status_by_email(email: str):
    try:
        response = users_table.scan(
            FilterExpression=Attr('email').eq(email)
        )
        
        items = response.get('Items', [])
        
        if not items:
            return None
        user = items[0]
        user_status = user.get('user_status', {}).get('S', None) if isinstance(user.get('user_status', {}), dict) else user.get('user_status')
        
        return user_status if user_status else "User status not found"
    
    except Exception as e:
        print(f"Error fetching user status: {str(e)}")
        return None

def get_hashed_password_by_email(email: str):
    response = credentials_table.scan(
        FilterExpression='email = :email', 
        ExpressionAttributeValues={':email': email}
    )
    items = response.get('Items', [])
    
    if items and isinstance(items[0], dict):
        return items[0].get('password')  
    
    return None  

def authenticate_user(email: str, password: str):
    hashed_password = get_hashed_password_by_email(email)
    if not hashed_password:
        return None

    if not verify_password(password, hashed_password):
        return None

    user = get_user_by_email(email)
    if not user:
        return None

    return user 

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise credentials_exception

    user = get_user_by_email(email)
    if user is None:
        raise credentials_exception
    return user 

def store_refresh_token(user_id: str, refresh_token: str):
    try:
        logging.info(f"Storing refresh token for user ID: {user_id}")
        credentials_table.update_item(
            Key={'user_id': user_id}, 
            UpdateExpression='SET refresh_token = :refresh_token',
            ExpressionAttributeValues={':refresh_token': refresh_token}
        )
        logging.info("Refresh token updated successfully.")
    except ClientError as e:
        logging.error(f"Error updating refresh token for user ID {user_id}: {e.response['Error']['Message']}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating refresh token")


def get_refresh_token_from_db(user_id: str):
    
    response = credentials_table.get_item(Key={'user_id': user_id})
    return response.get('Item', {}).get('refresh_token')

def delete_refresh_token(user_id: str):
    response = credentials_table.get_item(
        Key={'user_id': user_id} 
    )
    
    if 'Item' in response:
        item = response['Item']
        print("Retrieved item:", item)  
        
        if 'refresh_token' in item: 
            refresh_token = item['refresh_token']  
            print("Found refresh token:", refresh_token) 
            
            credentials_table.update_item(
                Key={'user_id': user_id},
                UpdateExpression="REMOVE refresh_token"
            )
            return {"detail": "Refresh token deleted successfully"}
        else:
            return {"detail": "No refresh token found for this user"}
    else:
        return {"detail": "User not found"}


def generate_password_reset_token(email: str, user_id: str):
    expire = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": email, "user_id": user_id, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def send_reset_verification_email(email,password,user_id):  
    reset_token = generate_password_reset_token(email, user_id)  
    subject = "Reset Your Password"
    message_text = f"""
    Hi there,

    We received a request to reset the password for your account. Click the link below to reset your password. This link will expire in 10 minutes.

    Reset Password: http://127.0.0.1:8080/reset-password/{reset_token}

    If you didn't request a password reset, you can ignore this email.

    Thanks,
    The Support Team
    """
    creds = None
    token_path = r'src\auth\token.pickle'
    creds_path = r'src\auth\cred.json'    
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request()) 
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=8080)
  
        with open(token_path, 'wb') as token_file:
            pickle.dump(creds, token_file)

    service = build('gmail', 'v1', credentials=creds)
    message = MIMEText(message_text)
    message['to'] = email  
    message['from'] = 'rameshdornala927@gmail.com'  
    message['subject'] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    try:
        service.users().messages().send(
            userId='me',
            body={'raw': raw_message}  
        ).execute()
        print(f"Verification email sent to your {email}")
        response = {
            "user_id" : user_id
        }
        return response
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        raise  


def userexists(username: str, email: str):
    try:
        response = users_table.scan(
            FilterExpression=Attr('username').eq(username) | Attr('email').eq(email)
        )
        return len(response['Items']) > 0
    except ClientError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error querying database")