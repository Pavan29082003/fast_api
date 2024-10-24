from fastapi import FastAPI, HTTPException, APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import boto3
from datetime import datetime
from typing import List
import uuid
import pytz
from src.settings import settings
from src.database.connections import connections


router = APIRouter()

users_table = connections.dynamodb.Table('UsersTable')
history_table = connections.dynamodb.Table('HistoryTable')

# Define models
class Interaction(BaseModel):
    user_question: str
    question_response: str

class Message(BaseModel):
    interactions: List[Interaction]

class EditTitleRequest(BaseModel):
    new_title: str      


# Retrieve all sessions for a user
@router.get("/conversations/{user_id}/sessions")
async def fetch_sessions(user_id: str):
    try:
        user_response = users_table.get_item(Key={'user_id': user_id})
        if 'Item' not in user_response:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "error", "message": f"User {user_id} not found in UsersTable."}
            )

        history_sessions = user_response['Item'].get('history_sessions', [])
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "success", "sessions": history_sessions}
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": f"An error occurred: {str(e)}"}
        )


# Retrieve conversation history for a session
@router.get("/conversations/{user_id}/{session_id}/history")
async def get_history(user_id: str, session_id: str):
    try:
        response = history_table.get_item(Key={'user_id': user_id, 'session_id': session_id})
        if 'Item' not in response:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "error", "message": "No conversation history found for the session."}
            )

        conversation = response['Item'].get('conversation', [])
        session_title = response['Item'].get('session_title', 'Untitled Session')

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "success", "session_title": session_title, "conversation": conversation }
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": f"An error occurred: {str(e)}"}
        )


# Edit a session title
@router.put("/conversations/{user_id}/{session_id}/edit")
async def edit_session_title(user_id: str, session_id: str, request: EditTitleRequest):
    try:
        user_response = users_table.get_item(Key={'user_id': user_id})
        if 'Item' not in user_response:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "error", "message": f"User {user_id} not found in UsersTable."}
            )
        
        user_item = user_response['Item']
        history_sessions = user_item.get('history_sessions', [])

        session_found = False
        for session in history_sessions:
            if session['session_id'] == session_id:
                session['session_title'] = request.new_title
                session_found = True
                break
        
        if not session_found:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "error", "message": f"Session {session_id} not found."}
            )

        users_table.update_item(
            Key={'user_id': user_id},
            UpdateExpression="SET history_sessions = :history_sessions",
            ExpressionAttributeValues={':history_sessions': history_sessions}
        )

        history_table.update_item(
            Key={'user_id': user_id, 'session_id': session_id},
            UpdateExpression="SET session_title = :new_title",
            ExpressionAttributeValues={':new_title': request.new_title}
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "success", "message": "Session title updated successfully."}
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": f"An error occurred: {str(e)}"}
        )


# Delete all messages for a specific session
@router.delete("/conversations/{user_id}/{session_id}/delete")
async def delete_session(user_id: str, session_id: str):
    try:
        response = history_table.scan(
            FilterExpression="user_id = :user_id AND session_id = :session_id",
            ExpressionAttributeValues={':user_id': user_id, ':session_id': session_id}
        )
        
        items_to_delete = response.get('Items', [])
        
        if not items_to_delete:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "error", "message": "No messages found for the given session."}
            )

        for item in items_to_delete:
            history_table.delete_item(
                Key={
                    'user_id': item['user_id'],
                    'session_id': item['session_id']
                }
            )

        user_response = users_table.get_item(Key={'user_id': user_id})
        if 'Item' not in user_response:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "error", "message": f"User {user_id} not found in UsersTable."}
            )

        user_item = user_response['Item']
        history_sessions = user_item.get('history_sessions', [])

        if session_id in [s['session_id'] for s in history_sessions]:
            history_sessions = [s for s in history_sessions if s['session_id'] != session_id]
            users_table.update_item(
                Key={'user_id': user_id},
                UpdateExpression="SET history_sessions = :history_sessions",
                ExpressionAttributeValues={':history_sessions': history_sessions}
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "success", "message": "Session and messages deleted successfully."}
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": f"An error occurred: {str(e)}"}
        )
