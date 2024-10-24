# app/config.py
from pydantic_settings import BaseSettings
import boto3

class Settings(BaseSettings):
    aws_secret_key: str
    aws_access_key: str
    debug_mode: bool = False 
    ip: str
    gemini_api_key : str

    class Config:
        env_file = ".env" 
   
settings = Settings()

