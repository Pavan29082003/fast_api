from datetime import datetime, timedelta, timezone
import jwt
import boto3
from passlib.context import CryptContext
from fastapi import (HTTPException, status,Depends, HTTPException,)
from fastapi.security import OAuth2PasswordBearer
from src.database.connections import connections

SECRET_KEY = "6fee615b2e2938c237f9cf7d49f7b55afb78ac626dd6c983f4cc125aecf22b070325b6eb9554893fc787f0d7154225bf02f324d244d7c9ce0a205cca82fcc02b8382ac8cd1c6126d43315a3da96d564951d72d0f3291f78bb2b9d9e372ed499fbf78f421c0dc0487642f94e08e545d1f1dc00423699cc66623981c8c902fe2a103d8825ab4bc03f7d8658eca8bc4f24c97bbc33277d7571f6bcfdd40c872e70054caf8a263fdbcb741932596d62fc85e68cbfa5eb9c8c237c09455bf8d5dcc34e2acfd584c8f0f785c7c9d1f23b9cab8cd78d5bcfa1f385556ba66fd26469dce8908414579bbe2cabc599ce9c5a1e58734333acc303572c1750a90f6e779c151"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
users_table = connections.dynamodb.Table('UsersTable')
credentials_table = connections.dynamodb.Table('CredentialsTable')

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user_by_email(email: str):
    response = credentials_table.scan(FilterExpression='email = :email', ExpressionAttributeValues={':email': email})
    items = response.get('Items', [])
    return items[0] if items else None

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


async def get_current_user(token: str = Depends(oauth2_scheme)):
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


def userexists(username: str, email: str):
    try:
        response = users_table.scan(
            FilterExpression=Attr('username').eq(username) | Attr('email').eq(email)
        )
        return len(response['Items']) > 0
    except ClientError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error querying database")

def verify_password(stored_password, provided_password):
    return bcrypt.verify(provided_password, stored_password)