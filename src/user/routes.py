from fastapi import APIRouter, HTTPException, status, Depends,UploadFile, File 
from pydantic import BaseModel
from typing import Optional
from fastapi.responses import JSONResponse
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from passlib.hash import bcrypt
from src.settings import settings
from src.database.connections import connections
import uuid
from boto3.dynamodb.conditions import Key, Attr
from src.dashboard.utils import(get_user_role, has_permission_to_create, userexists,
 get_user_by_id,has_permission_to_get_users, get_users_by_role,get_user_details,
)
from src.auth.utils import (get_current_user,send_verification_email,)
from .models import EditUserProfileRequest

load_dotenv()
router=APIRouter()
users_table = connections.dynamodb.Table('UsersTable')
credentials_table = connections.dynamodb.Table('CredentialsTable')
roles_table = connections.dynamodb.Table('RolesTable')
BUCKET_NAME = 'userprofilepicturess' 

s3_client = boto3.client(
    's3',
    aws_access_key_id=settings.aws_access_key,
    aws_secret_access_key=settings.aws_secret_key,
)


@router.get("/profile/{user_id}")
async def get_user_profile(user_id: str, current_user: dict = Depends(get_current_user)):
    user_profile = await get_user_by_id(user_id)  
    return {"user_profile": user_profile}


@router.put("/edit_user_profile")
async def edit_user(request: EditUserProfileRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user['user_id']
    
    try:
        response = users_table.query(
            KeyConditionExpression=Key('user_id').eq(user_id)
        )
        if not response.get('Items'):
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = response['Items'][0]

        if request.email and request.email != user_data['email']:
            email_exists = users_table.scan(
                FilterExpression=Attr('email').eq(request.email) & Attr('user_id').ne(user_id)
            )
            if email_exists['Count'] > 0:
                raise HTTPException(status_code=400, detail="Email already exists")
        
        update_expression = []
        expression_attribute_values = {}

    
        if request.username:  
            update_expression.append("username = :username")
            expression_attribute_values[":username"] = request.username
        
        if request.email:
            update_expression.append("email = :email")
            expression_attribute_values[":email"] = request.email
        

        if update_expression:
            users_table.update_item(
                Key={'user_id': user_id},
                UpdateExpression="SET " + ", ".join(update_expression),
                ExpressionAttributeValues=expression_attribute_values
            )

        if request.email or request.password:
            credentials_update = {}
            if request.email:
                credentials_update['email'] = request.email

            if request.password:
                hashed_password = bcrypt.hash(request.password)
                credentials_update['password'] = hashed_password

            if credentials_update:
                credentials_table.update_item(
                    Key={'user_id': user_id},
                    UpdateExpression="SET " + ", ".join([f"{key} = :{key}" for key in credentials_update]),
                    ExpressionAttributeValues={f":{key}": value for key, value in credentials_update.items()}
                )

        return {"message": "User details updated successfully"}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update user: {str(e)}")




@router.post("/upload_profile_picture/")
async def upload_profile_picture(user_id: str, file: UploadFile = File(...),current_user: dict = Depends(get_current_user)):
    try:
        
        user_response = users_table.get_item(Key={'user_id': user_id})
        if 'Item' not in user_response:
            raise HTTPException(status_code=404, detail="User not found")
        
    
        file_extension = file.filename.split('.')[-1]
        unique_filename = f"profile_pictures/{user_id}_{uuid.uuid4()}.{file_extension}"
        
        s3_client.upload_fileobj(file.file, BUCKET_NAME, unique_filename)

        s3_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{unique_filename}"

        users_table.update_item(
            Key={'user_id': user_id},
            UpdateExpression="SET profile_picture_url = :url",
            ExpressionAttributeValues={':url': s3_url}
        )

        return {"message": "Profile picture uploaded successfully", "url": s3_url}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload profile picture: {str(e)}")

@router.delete("/delete_profile_picture")
async def delete_profile_picture(user_id: str,current_user: dict = Depends(get_current_user)):
    try:
    
        user_response = users_table.get_item(Key={'user_id': user_id})
        if 'Item' not in user_response:
            raise HTTPException(status_code=404, detail="User not found")
        
        current_picture_url = user_response['Item'].get('profile_picture_url')
        if not current_picture_url:
            raise HTTPException(status_code=404, detail="No profile picture found")

        filename_to_delete = current_picture_url.split('/')[-1]

        s3_client.delete_object(Bucket=BUCKET_NAME, Key=f"profile_pictures/{filename_to_delete}")

        users_table.update_item(
            Key={'user_id': user_id},
            UpdateExpression="REMOVE profile_picture_url"
        )

        return {"message": "Profile picture deleted successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete profile picture: {str(e)}")
