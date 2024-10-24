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
from datetime import datetime


from boto3.dynamodb.conditions import Key, Attr
from src.dashboard.utils import( has_permission_to_create, userexists,
 get_user_by_id,has_permission_to_get_users,get_user_details,get_user_role, get_users_by_organization,generate_random_password,
)
from .models import (BaseModel,UpdateStatusRequest,EditUserRequest,UserCreationRequest,)
from src.auth.utils import (get_current_user,send_verification_email, generate_password_reset_token)


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

@router.post("/create-user/{creator_id}")
async def create_user(creator_id: str, request: UserCreationRequest, current_user: dict = Depends(get_current_user)):
    try:
        creator_role = get_user_role(creator_id)

        if not has_permission_to_create(creator_role, request.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{creator_role}s are not allowed to create {request.role}s."
            )

        user_id = str(uuid.uuid4())
        username = request.username
        email = request.email
        password=generate_random_password()
        hashed_password = bcrypt.hash(password)
        technical_skills = request.technical_skills
        research_interests = request.research_interests
        primary_research_area=request.primary_research_area
        role =request.role
        department = request.department
        organization_name = request.organization_name

        if userexists(username, email):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={'msg': "User already exists with the same username or email"}
            )

        current_time = datetime.utcnow().isoformat()
        
        users_table.put_item(
            Item={
                'user_id': user_id,
                'username': username,
                'email': email,
                'department': department,
                'organization_name': organization_name,
                'user_status': "active",
                'research_interests': research_interests,
                "primary_research_area": primary_research_area,
                'technical_skills': technical_skills,
                "current_time":current_time
            }
        )
        credentials_table.put_item(
            Item={
                'user_id': user_id,
                'email': email,
                'password': hashed_password,  
            }
        )

        roles_table.put_item(
            Item={
                'user_id': user_id,
                'role': "User"
            }
        )

        send_verification_email(email,password,user_id)
        reset_token = generate_password_reset_token(email, user_id) 

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                'status': 'success',
                'message': 'A verification and password reset email has been sent.',
                'data': {'email': request.email, "reset_token":reset_token}
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all_users/{admin_id}/{organization_name}")
async def get_users_with_role(admin_id: str, organization_name: str, current_user: dict = Depends(get_current_user)):
    current_user_role =  get_users_by_organization(admin_id) 
    
    if not has_permission_to_get_users(current_user_role, role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view users of this role."
        )
    
    users = await  get_users_by_organization(organization_name)
    users_with_details = []
    for user in users:
        user_details = await get_user_details(user["user_id"]) 
        users_with_details.append({
            "organization_name": user["organization_name"],
            "user_id": user["user_id"],
            "email": user_details.get("email"),       
            "user_status": user_details.get("user_status") 
        })

    return {"users": users_with_details}

@router.put("/update_user_status")
async def update_user_status(request: UpdateStatusRequest, current_user: dict = Depends(get_current_user)):
    admin_id = request.admin_id
    user_id = request.user_id
    new_status = request.status
    current_user_role = get_user_role(admin_id)
    target_user_role = get_user_role(user_id)

    response = users_table.query(
        KeyConditionExpression=Key('user_id').eq(user_id)
    )
    
    if not response.get('Items'):
        raise HTTPException(status_code=404, detail="User not found")
    
    if current_user_role != 'Admin' and target_user_role == 'Super Admin':
        raise HTTPException(status_code=403, detail="You do not have permission to update a superadmin.")
    
    if current_user_role == 'Admin' and target_user_role != 'User':
        raise HTTPException(status_code=403, detail="Admins can only update regular users.")

    try:
        users_table.update_item(
            Key={'user_id': user_id},
            UpdateExpression="SET user_status = :status",
            ExpressionAttributeValues={':status': new_status}
        )
        return {"message": f"User {user_id} status updated to {new_status}"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")

@router.delete("/delete_user/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    admin_id = current_user['user_id']
    print(admin_id)  
    current_user_role = get_user_role(admin_id)
    target_user_role = get_user_role(user_id)

    response = users_table.query(
        KeyConditionExpression=Key('user_id').eq(user_id)
    )
    
    if not response.get('Items'):
        raise HTTPException(status_code=404, detail="User not found")
    
    if current_user_role != 'Super Admin' and target_user_role == 'Super Admin':
        raise HTTPException(status_code=403, detail="You do not have permission to delete a superadmin.")
    
    if current_user_role == 'Admin' and target_user_role != 'User':
        raise HTTPException(status_code=403, detail="Admins can only delete regular users.")

    try:
        users_table.delete_item(
            Key={'user_id': user_id}
        )
        return {"message": f"User {user_id} successfully deleted."}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")


@router.put("/edit_user")
async def edit_user(request: EditUserRequest, current_user: dict = Depends(get_current_user)):
    admin_id = current_user['user_id']
    user_id = request.user_id
    new_email = request.new_email
    new_password = request.new_password
    new_status = request.new_status
    new_role = request.new_role
    
    current_user_role = get_user_role(admin_id)
    target_user_role = get_user_role(user_id)
    
    
    response = users_table.query(
        KeyConditionExpression=Key('user_id').eq(user_id)
    )
    
    if not response.get('Items'):
        raise HTTPException(status_code=404, detail="User not found")
    
    if current_user_role != 'Admin' and target_user_role == 'Super Admin':
        raise HTTPException(status_code=403, detail="You do not have permission to edit a superadmin.")
    
    if current_user_role == 'Admin' and target_user_role != 'User':
        raise HTTPException(status_code=403, detail="Admins can only edit regular users.")
    
    
    try:
        if new_email:
            users_table.update_item(
                Key={'user_id': user_id},
                UpdateExpression="SET email = :email",
                ExpressionAttributeValues={':email': new_email}
            )
        
        if new_password:
            credentials_table.update_item(
                Key={'user_id': user_id},
                UpdateExpression="SET password = :password",
                ExpressionAttributeValues={':password': new_password}
            )
        
        if new_status:
            users_table.update_item(
                Key={'user_id': user_id},
                UpdateExpression="SET user_status = :status",
                ExpressionAttributeValues={':status': new_status}
            )
        
        
        if new_role:
            roles_table.update_item(
                Key={'user_id': user_id},
                UpdateExpression="SET #rl = :role",
                ExpressionAttributeNames={'#rl': 'role'},  
                ExpressionAttributeValues={':role': new_role}
            )
        
        return {"message": f"User {user_id} updated successfully."}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")




