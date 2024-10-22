from fastapi import FastAPI, HTTPException, APIRouter, status, Query
from fastapi.responses import JSONResponse
import boto3
from src.settings import settings

app = FastAPI()
router = APIRouter()

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1',
    aws_access_key_id=settings.aws_access_key,
    aws_secret_access_key=settings.aws_secret_key
)

# DynamoDB table for users
users_table = dynamodb.Table('UsersTable')

# Add article to bookmarks
@router.post("/users/{user_id}/bookmarks")
async def add_bookmark(user_id: str, article_id: str = Query(...)):
    try:
        user_data = users_table.get_item(Key={'user_id': user_id})
        
        if 'Item' not in user_data:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={'status': 'error', 'message': f"User {user_id} not found in UsersTable"}
            )

        bookmarks = user_data['Item'].get('bookmarks', [])

       
        if article_id in bookmarks:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={'status': 'error', 'message': f"Article {article_id} is already bookmarked"}
            )
        bookmarks.append(article_id)
        users_table.update_item(
            Key={'user_id': user_id},
            UpdateExpression="SET bookmarks = :bookmarks",
            ExpressionAttributeValues={':bookmarks': bookmarks}
        )

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={'status': 'success', 'message': f"Article {article_id} bookmarked successfully"}
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'status': 'error', 'message': f"An error occurred: {str(e)}"}
        )


# Get all bookmarks for a user
@router.get("/users/{user_id}/bookmarks")
async def get_bookmarks(user_id: str):
    try:
        user_data = users_table.get_item(Key={'user_id': user_id})
        
        if 'Item' not in user_data:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={'status': 'error', 'message': f"User {user_id} not found in UsersTable"}
            )
        
        bookmarks = user_data['Item'].get('bookmarks', [])

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'status': 'success', 'bookmarks': bookmarks}
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'status': 'error', 'message': f"An error occurred: {str(e)}"}
        )

@router.delete("/users/{user_id}/bookmarks")
async def remove_bookmark(user_id: str, article_id: str = Query(...)):
    try:
        user_data = users_table.get_item(Key={'user_id': user_id})
        
        if 'Item' not in user_data:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={'status': 'error', 'message': f"User {user_id} not found in UsersTable"}
            )

        bookmarks = user_data['Item'].get('bookmarks', [])
        if article_id not in bookmarks:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={'status': 'error', 'message': f"Article {article_id} not found in bookmarks"}
            )

        bookmarks.remove(article_id)

        users_table.update_item(
            Key={'user_id': user_id},
            UpdateExpression="SET bookmarks = :bookmarks",
            ExpressionAttributeValues={':bookmarks': bookmarks}
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'status': 'success', 'message': f"Article {article_id} removed from bookmarks"}
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'status': 'error', 'message': f"An error occurred: {str(e)}"}
        )

