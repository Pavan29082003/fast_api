# app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    aws_secret_key: str
    aws_access_key: str
    debug_mode: bool = False 

    class Config:
        env_file = ".env"  # Path to your .env file

settings = Settings()

