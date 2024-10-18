from flask import Flask, request, jsonify
import uuid
import boto3
from werkzeug.security import generate_password_hash, check_password_hash
import os.path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from boto3.dynamodb.conditions import Key
import base64
from flask_jwt_extended import create_access_token, set_access_cookies
from flask_jwt_extended import  JWTManager
from werkzeug.security import check_password_hash
from flask import request, jsonify
import pickle

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def send_verification_email(email,password,user_id):    
    subject = "Super Admin Account Created: Verify and Reset Password"
    message_text = f"""
    Dear User,
    Your account has been successfully created. Please use the following link to verify your email and reset your password:
    Your current password is: {password}
    Verification and Password Reset Link:
    http://127.0.0.1:8080/reset-password/{user_id}

    If you did not create this account, please contact our support team immediately.

    Regards,
    Research Team
    """
    creds = None
    token_path = r'C:\Users\Ramesh Dornala\Desktop\fast_app\src\auth\token.pickle'
    creds_path = r'C:\Users\Ramesh Dornala\Desktop\fast_app\src\auth\cred.json'
    
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
    
    

    

