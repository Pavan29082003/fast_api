from fastapi import FastAPI, HTTPException, APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import boto3, uuid
from datetime import datetime
import pytz
from src.settings import settings


router = APIRouter()

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1',
    aws_access_key_id=settings.aws_access_key,
    aws_secret_access_key=settings.aws_secret_key
)

credentials_table = dynamodb.Table('UsersTable')
notes_table = dynamodb.Table('NotesTable')

class NoteCreate(BaseModel):
    title: str
    content: str

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

def get_local_time_formatted():
    local_timezone = pytz.timezone('Asia/Kolkata')
    local_time = datetime.now(local_timezone)
    return local_time.strftime('%d-%m-%Y %H:%M')

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
