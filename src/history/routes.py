from fastapi import FastAPI, HTTPException, APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import boto3
from datetime import datetime
from typing import List
import uuid
from src.settings import settings

app = FastAPI()
router = APIRouter()

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1',
    aws_access_key_id=settings.aws_access_key,
    aws_secret_access_key=settings.aws_secret_key
)

users_table = dynamodb.Table('UsersTable')
history_table = dynamodb.Table('HistoryTable')

class Interaction(BaseModel):
    user_question: str
    question_response: str

class Message(BaseModel):
    interactions: List[Interaction]  # Expecting a list of interactions

def get_timestamp():
    return datetime.utcnow().strftime("%d-%m-%Y %H:%M")

# Store a conversation message in a session
@router.post("/conversations/{user_id}/create")
async def store_message(user_id: str, message: Message):
    try:
        # Generate a new session_id automatically using uuid4
        session_id = str(uuid.uuid4())

        user_response = users_table.get_item(Key={'user_id': user_id})
        if 'Item' not in user_response:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "error", "message": f"User {user_id} not found in UsersTable."}
            )
        
        user_item = user_response['Item']
        history_sessions = user_item.get('history_sessions', [])
        
        if session_id not in history_sessions:
            history_sessions.append(session_id)
            users_table.update_item(
                Key={'user_id': user_id},
                UpdateExpression="SET history_sessions = :history_sessions",
                ExpressionAttributeValues={':history_sessions': history_sessions}
            )

        # Step 2: Store the conversation in the HistoryTable
        timestamp = get_timestamp()
        ordered_conversation = [
            {
                'user_question': interaction.user_question,
                'question_response': interaction.question_response
            } for interaction in message.interactions
        ]

        history_table.put_item(
            Item={
                'user_id': user_id,
                'session_id': session_id,
                'timestamp': timestamp,
                'conversation': ordered_conversation
            }
        )
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"status": "success", "message": "Conversation stored successfully.", "session_id": session_id}
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

        # Reorder conversation to ensure user_question comes before question_response in every interaction
        ordered_conversation = [
            {
                'user_question': interaction['user_question'],
                'question_response': interaction['question_response']
            } for interaction in conversation
        ]

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "success", "conversation": ordered_conversation}
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
        # First, delete all messages from HistoryTable for the session_id
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

        # Remove session_id from UsersTable
        user_response = users_table.get_item(Key={'user_id': user_id})
        if 'Item' not in user_response:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "error", "message": f"User {user_id} not found in UsersTable."}
            )

        user_item = user_response['Item']
        history_sessions = user_item.get('history_sessions', [])

        if session_id in history_sessions:
            history_sessions.remove(session_id)
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
