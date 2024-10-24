import random
from pydantic import BaseModel, Field
from typing import List,Optional



class UserCreationRequest(BaseModel):
    username: str
    email: str 
    department: str
    primary_research_area: str
    organization_name: str
    job_title:str
    technical_skills: List[str] 
    role :str
    research_interests: List[str]  


class UpdateStatusRequest(BaseModel):
    admin_id:str
    user_id: str
    status: str 

class  EditUserRequest(BaseModel):
    user_id :str
    new_email :Optional[str]=None
    new_password :Optional[str]=None
    new_status : Optional[str]=None
    new_role :Optional[str]=None
