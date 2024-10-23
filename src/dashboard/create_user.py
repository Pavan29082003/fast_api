from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
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
from src.auth.utils import (get_current_user,)



load_dotenv()
router=APIRouter()
users_table = connections.dynamodb.Table('UsersTable')
credentials_table = connections.dynamodb.Table('CredentialsTable')
roles_table = connections.dynamodb.Table('RolesTable')

class UserCreationRequest(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: str
    phone_number: str
    password: str
    role: str
    organization_name: str
    user_status: str

class UpdateStatusRequest(BaseModel):
    admin_id:str
    user_id: str
    status: str 

@router.post("/create-user/{creator_id}")
async def create_user(creator_id: str, request: UserCreationRequest):
    try:
        creator_role = get_user_role(creator_id)

        if not has_permission_to_create(creator_role, request.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{creator_role}s are not allowed to create {request.role}s."
            )

        user_id = str(uuid.uuid4())
        first_name = request.first_name
        last_name = request.last_name
        username = request.username
        email = request.email
        phone_number = request.phone_number
        password = request.password
        hashed_password = bcrypt.hash(password)
        organization_name = request.organization_name
        user_status=request.user_status
        role = request.role

        if userexists(username, email):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={'msg': "User already exists with the same username or email"}
            )

        users_table.put_item(
            Item={
                'user_id': user_id,
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'email': email,
                'phone_number': phone_number,
                'organization_name': organization_name,
                'user_status':user_status
            }
        )

        credentials_table.put_item(
            Item={
                'user_id': user_id,
                'email'  :email,
                'password': hashed_password,
                
            }
        )

        roles_table.put_item(
            Item={
                'user_id': user_id,
                'role': role
            }
        )

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                'status': 'success',
                'message': f'{role} created successfully.',
                'data': {'email': request.email}
            }
        )

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



@router.get("/profile/{user_id}")
async def get_user_profile(user_id: str, current_user: dict = Depends(get_current_user)):
    user_profile = await get_user_by_id(user_id)  
    return {"user_profile": user_profile}


@router.get("/all_users/{admin_id}/{role}")
async def get_users_with_role(admin_id: str, role: str, current_user: dict = Depends(get_current_user)):
    current_user_role = get_user_role(admin_id) 
    
    if not has_permission_to_get_users(current_user_role, role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view users of this role."
        )
    
    users = await get_users_by_role(role)
    users_with_details = []
    for user in users:
        user_details = await get_user_details(user["user_id"]) 
        users_with_details.append({
            "role": user["role"],
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
