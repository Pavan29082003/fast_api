from fastapi import FastAPI, Request, Response, APIRouter, status
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional
from pydantic import BaseModel
from src.view_article import utils
from src.settings import settings
import boto3
from datetime import datetime
from src.database.connections import connections

router = APIRouter()

class QuestionRequest(BaseModel):
    question: str
    user_id: str
    session_id: Optional[str] = None
    source: str
    article_id: int

@router.get("/get_article/{article_id}")
async def get_article(article_id : str, source : str):
    
    response  = await utils.get_article(article_id,source)
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status" : "success",
            "article" : response
            }
    )    
    
@router.post("/generateanswer")
async def get_answer(request: QuestionRequest):
    question = request.question
    session_id = request.session_id
    source = request.source
    article_id = request.article_id
    user_id = request.user_id
    
    user_response = connections.users_table.get_item(Key={'user_id': user_id})
    if 'Item' not in user_response:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"status": "error", "message": f"User {user_id} not found in UsersTable."}
        )
    
    user_item = user_response['Item']
    history_sessions = user_item.get('history_sessions', [])

    if not session_id:
        session_id = utils.create_session()
        session_title = f"{question[:100]}"  # Limit title to 100 characters
        history_sessions.append({'session_id': session_id, 'session_title': session_title})
        connections.users_table.update_item(
            Key={'user_id': user_id},
            UpdateExpression="SET history_sessions = :history_sessions",
            ExpressionAttributeValues={':history_sessions': history_sessions}
        )
        
    timestamp = datetime.now().strftime("%d-%m-%Y %H:%M")

    history = connections.history_table.get_item(Key={'user_id': user_id, 'session_id': session_id})
    history = history.get('Item', {})
    session_title = history.get("session_title",question)
    previous_conversations = history.get('conversation',[])
    print(previous_conversations)
    response_generator = utils.answer_query(question, article_id, session_id, source, previous_conversations)
    
    async def stream_response():
        for response in response_generator:
            print(type(response))
            if isinstance(response,bytes):
                print("yes")
                yield response
            last_response = response
        print(last_response)
        connections.history_table.put_item(
            Item={
                'user_id': user_id,
                'session_id': session_id,
                'timestamp': timestamp,
                'conversation': last_response,
                'session_title': session_title,
                'article_id': article_id,
                'source': source
            }
        )
    
    return StreamingResponse(stream_response(), media_type="application/json")
