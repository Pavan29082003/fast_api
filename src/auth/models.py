from pydantic import BaseModel 
from typing import Optional

class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: str
    phone_number: str
    password: str
    role: str
    department:str
    organization_name: str
    user_status: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

class LoginData(BaseModel):
    email: str
    password: str
class RefreshTokenData(BaseModel):
    refresh_token: str

class PasswordResetData(BaseModel):
    new_password:str
    confirm_password:str

class EmailData(BaseModel):
    email: str

class PasswordResetData(BaseModel):
    new_password: str
    confirm_password: str
