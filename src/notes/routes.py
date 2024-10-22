from fastapi import FastAPI, HTTPException, APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import boto3, uuid
from datetime import datetime
import pytz
from twilio.rest import Client
from src.settings import settings
import os
import base64
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1',
    aws_access_key_id=settings.aws_access_key,
    aws_secret_access_key=settings.aws_secret_key
)


credentials_table = dynamodb.Table('UsersTable')
notes_table = dynamodb.Table('NotesTable')


SCOPES = ['https://www.googleapis.com/auth/gmail.send']

class NoteCreate(BaseModel):
    title: str
    content: str

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class NoteShareEmail(BaseModel):
    email: str

def get_local_time_formatted():
    local_timezone = pytz.timezone('Asia/Kolkata')
    local_time = datetime.now(local_timezone)
    return local_time.strftime('%d-%m-%Y %H:%M')

def fetch_note(user_id: str, note_id: str):
    response = notes_table.get_item(Key={'user_id': user_id})
    user_data = response.get('Item')
    
    if not user_data or note_id not in user_data:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found for user {user_id}")
    
    return user_data[note_id]

# Helper function to send email using Gmail API
def send_email(email: str, subject: str, message_html: str):
    creds = None
    token_path = r'C:\Users\saina\OneDrive\Desktop\fast_api\src\auth\token.pickle'  
    creds_path = r'C:\Users\saina\OneDrive\Desktop\fast_api\cred.json'  

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

    message = MIMEText(message_html, 'html')  
    message['to'] = email
    message['from'] = 'rameshdornala927@gmail.com'    
    message['subject'] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

    try:
        service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        print(f"Email sent to {email}")
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    
# 1. Create a new note for a user
@router.post("/users/{user_id}/createnotes")
async def create_note(user_id: str, note: NoteCreate):
    note_id = str(uuid.uuid4())
    timestamp = get_local_time_formatted()

    try:
        credentials_response = credentials_table.get_item(Key={'user_id': user_id})
        if 'Item' not in credentials_response:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    'status': 'error',
                    'message': f"User with id {user_id} not found in UsersTable"
                }
            )
        
        notes_response = notes_table.get_item(Key={'user_id': user_id})
        user_data = notes_response.get('Item', {})

        user_data['user_id'] = user_id
        user_data[note_id] = {
            'note_id': note_id,
            'title': note.title,
            'content': note.content,
            'created_at': timestamp,
            'last_updated_at': timestamp
        }

        notes_table.put_item(Item=user_data)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                'status': 'success',
                'message': 'Note created successfully.',
                'data': {
                    'note_id': note_id,
                    'user_id': user_id,
                    'title': note.title,
                    'content': note.content,
                    'created_at': timestamp
                }
            }
        )
    
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                'status': 'error',
                'message': f"An error occurred: {str(e)}"
            }
        )

# 2. Get all notes for a user from NotesTable
@router.get("/users/{user_id}/getnotes")
async def get_user_notes(user_id: str):
    try:
        response = notes_table.get_item(Key={'user_id': user_id})
        user_data = response.get('Item')

        if not user_data:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    'status': 'error',
                    'message': f"No notes found for user {user_id}"
                }
            )

        notes = {k: v for k, v in user_data.items() if k != 'user_id'}
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                'status': 'success',
                'message': f"Notes retrieved for user {user_id}",
                'data': notes
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                'status': 'error',
                'message': f"An error occurred: {str(e)}"
            }
        )

# 3. Update a specific note for a user
@router.put("/users/{user_id}/{note_id}/updatenotes/")
async def update_note(user_id: str, note_id: str, note: NoteUpdate):
    try:
        response = notes_table.get_item(Key={'user_id': user_id})
        user_data = response.get('Item')

        if not user_data or note_id not in user_data:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    'status': 'error',
                    'message': f"Note {note_id} not found for user {user_id}"
                }
            )
        
        if note.title:
            user_data[note_id]['title'] = note.title
            
        if note.content:
            user_data[note_id]['content'] = note.content

        user_data[note_id]['last_updated_at'] = get_local_time_formatted()

        notes_table.put_item(Item=user_data)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                'status': 'success',
                'message': 'Note updated successfully.',
                'data': {
                    'note_id': note_id,
                    'title': user_data[note_id]['title'],
                    'content': user_data[note_id]['content'],
                    'last_updated_at': user_data[note_id]['last_updated_at']
                }
            }
        )
    
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                'status': 'error',
                'message': f"An error occurred: {str(e)}"
            }
        )

# 4. Delete a specific note for a user
@router.delete("/users/{user_id}/{note_id}/deletenotes")
async def delete_note(user_id: str, note_id: str):
    try:
        response = notes_table.get_item(Key={'user_id': user_id})
        user_data = response.get('Item')

        if not user_data or note_id not in user_data:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    'status': 'error',
                    'message': f"Note {note_id} not found for user {user_id}"
                }
            )

        del user_data[note_id]

        notes_table.put_item(Item=user_data)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                'status': 'success',
                'message': 'Note deleted successfully.'
            }
        )
    
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                'status': 'error',
                'message': f"An error occurred: {str(e)}"
            }
        )

#email

@router.post("/users/{user_id}/{note_id}/sharenotes")
async def share_note_email(user_id: str, note_id: str, email_request: NoteShareEmail):
    try:
    
        note = fetch_note(user_id, note_id)

        message_html = f"""
        <html>
        <head>
            <style>
                body {{
                        font-family: 'Arial', sans-serif;
                        margin: 0;
                        padding: 0;
                        background-color: #f4f4f4;
                        background-image: url("life.jpeg");
                        background-size: cover; 
                        background-repeat: no-repeat;
                    }}
                .container {{
                    width: 80%;
                    max-width: 600px;
                    margin: 20px auto;
                    background-color: #ffffff;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                    padding: 0;
                    position: relative;
                    z-index: 1;
                }}
                h2 {{
                    color: #1d3557;
                    font-size: 28px;
                    text-align: center;
                    margin-top: 20px;
                }}
                .note-title {{
                    font-size: 20px;
                    color: #457b9d;
                    margin-bottom: 10px;
                    padding-left: 20px;
                }}
                .note-content {{
                    font-size: 16px;
                    color: #343a40;
                    padding: 20px;
                    border-left: 5px solid #1d3557;
                    background-color: #f1faee;
                    margin-bottom: 20px;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }}
                .footer {{
                    text-align: center;
                    font-size: 12px;
                    color: #6c757d;
                    padding: 20px;
                }}
                .footer p {{
                    margin: 0;
                    line-height: 1.5;
                }}
                .highlight {{
                    color: #e63946;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Shared Note from Notes App</h2>
                <p class="note-title"><span class="highlight">Title:</span> {note['title']}</p>
                <div class="note-content">
                    {note['content']}
                </div>
                <div class="footer">
                    <p>Shared via <strong>Notes App</strong></p>
                    <hr style="border: 0; border-top: 1px solid #ddd; width: 60%; margin: 20px auto;" />
                    <p>This is an auto-generated email. Please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Prepare the subject
        subject = f"Shared Note: {note['title']}"

        # Send the email using the helper function
        send_email(email_request.email, subject, message_html)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'status': 'success', 'message': 'Note shared via email successfully.'}
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'status': 'error', 'message': f"An error occurred: {str(e)}"}
        )