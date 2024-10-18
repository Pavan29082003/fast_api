from fastapi import FastAPI, HTTPException , APIRouter
from pydantic import BaseModel
from typing import Dict, Any, Optional
import boto3,uuid
from datetime import datetime
import pytz
from src.settings import settings


app = FastAPI()

router = APIRouter()

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1',
    aws_access_key_id=settings.aws_access_key,
    aws_secret_access_key=settings.aws_secret_key
)

table = dynamodb.Table('NotesTable')

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

@app.post("/users/{user_id}/notes/")
async def create_note(user_id: str, note: NoteCreate):
    note_id = str(uuid.uuid4())
    timestamp = get_local_time_formatted()
    try:
        response = table.get_item(Key={'user_id': user_id})
        user_data = response.get('Item', {})
        user_data['user_id'] = user_id
        user_data[note_id] = {
            'note_id': note_id,
            'title': note.title,
            'content': note.content,
            'created_at': timestamp,
            'last_updated_at': timestamp
        }
        table.put_item(Item=user_data)
        return {"user_id": user_id,"message": "Note created successfully", "note_id": note_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/notes/")
async def get_user_notes(user_id: str):
    try:
        response = table.get_item(Key={'user_id': user_id})
        user_data = response.get('Item')
        if not user_data:
            raise HTTPException(status_code=404, detail="No notes found for this user")
        notes = {k: v for k, v in user_data.items() if k != 'user_id'}
        return notes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/users/{user_id}/notes/{note_id}")
async def update_note(user_id: str, note_id: str, note: NoteUpdate):
    try:
        response = table.get_item(Key={'user_id': user_id})
        user_data = response.get('Item')

        if not user_data or note_id not in user_data:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found for user {user_id}")
        
        if note.title:
            user_data[note_id]['title'] = note.title

        if note.content:
            user_data[note_id]['content'] = note.content

        user_data[note_id]['last_updated_at'] = get_local_time_formatted()
        table.put_item(Item=user_data)
        
        return {"message": "Note updated successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/users/{user_id}/notes/{note_id}")
async def delete_note(user_id: str, note_id: str):
    try:
        response = table.get_item(Key={'user_id': user_id})
        user_data = response.get('Item')

        if not user_data or note_id not in user_data:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found for user {user_id}")
        
        del user_data[note_id]
        table.put_item(Item=user_data)
        return {"message": "Note deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
