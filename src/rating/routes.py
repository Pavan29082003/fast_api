from fastapi import FastAPI, HTTPException, APIRouter, status, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import boto3
from datetime import datetime
from src.settings import settings
from decimal import Decimal
from src.database.connections import connections
import pytz


def get_local_time_formatted():
    local_timezone = pytz.timezone('Asia/Kolkata')
    local_time = datetime.now(local_timezone)
    return local_time.strftime('%d-%m-%Y %H:%M')

router = APIRouter()


users_table = connections.dynamodb.Table('UsersTable')
ratings_table = connections.dynamodb.Table('RatingTable')

class RatingCreate(BaseModel):
    rating: int 

def convert_decimal_to_float(data):
    if isinstance(data, list):
        return [convert_decimal_to_float(item) for item in data]
    elif isinstance(data, dict):
        return {k: convert_decimal_to_float(v) for k, v in data.items()}
    elif isinstance(data, Decimal):
        return float(data)
    else:
        return data


@router.post("/{article_id}/rate")
async def rate_article(article_id: str, user_id: str = Query(...), rating: RatingCreate = None):
    if not (1 <= rating.rating <= 5):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rating must be between 1 and 5")

    try:
        
        user_response = users_table.get_item(Key={'user_id': user_id})
        if 'Item' not in user_response:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={'status': 'error', 'message': f"User {user_id} not found in UsersTable"}
            )

        
        user_item = user_response['Item']
        article_ids = user_item.get('article_ids', [])

        if article_id in article_ids:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={'status': 'error', 'message': f"User {user_id} has already rated article {article_id}"}
            )

        
        article_ids.append(article_id)

       
        users_table.update_item(
            Key={'user_id': user_id},
            UpdateExpression="SET article_ids = :article_ids",
            ExpressionAttributeValues={':article_ids': article_ids}
        )

       
        time_rated = get_local_time_formatted()
        ratings_table.put_item(
            Item={
                'user_id': user_id,  
                'article_id': article_id,
                'rating': rating.rating,
                'time_rated': time_rated
            }
        )

        
        article_data = ratings_table.get_item(Key={'user_id': article_id})  

        if 'Item' in article_data:
            rated_by = article_data['Item'].get('rated_by', [])
            total_ratings_sum = Decimal(article_data['Item'].get('total_ratings_sum', 0))
            total_ratings_count = article_data['Item'].get('total_ratings_count', 0)
        else:
            rated_by = []
            total_ratings_sum = Decimal(0)
            total_ratings_count = 0

       
        rated_by.append({
            "user_id": user_id,
            "rating": rating.rating,
            "time": time_rated
        })

       
        total_ratings_sum += Decimal(rating.rating)
        total_ratings_count += 1
        average_rating = total_ratings_sum / total_ratings_count

     
        ratings_table.put_item(
            Item={
                'user_id': article_id,  
                'rated_by': rated_by,  
                'total_ratings_sum': total_ratings_sum,
                'total_ratings_count': total_ratings_count,
                'average': average_rating
            }
        )

        
        response_data = {
            'user_id': user_id,
            'article_id': article_id,
            'rating': rating.rating,
            'average_rating': float(average_rating),
            'total_ratings_count': total_ratings_count,
            'rated_by': rated_by 
        }

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                'status': 'success',
                'message': f"Article {article_id} rated successfully by user {user_id}.",
                'data': convert_decimal_to_float(response_data)
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'status': 'error', 'message': f"An error occurred: {str(e)}"}
        )


@router.get("/{article_id}/average")
async def get_article_average_rating(article_id: str):
    try:
       
        article_data = ratings_table.get_item(Key={'user_id': article_id})  

        if 'Item' not in article_data:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={'status': 'error', 'message': f"No ratings found for article {article_id}"}
            )

      
        response_data = {
            'article_id': article_id,
            'average_rating': article_data['Item']['average'],
            'total_ratings_count': article_data['Item']['total_ratings_count'],
            'rated_by': article_data['Item']['rated_by']  
        }
        response_data = convert_decimal_to_float(response_data)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                'status': 'success',
                'data': response_data
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'status': 'error', 'message': f"An error occurred: {str(e)}"}
        )
