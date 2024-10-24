from pydantic import BaseModel 
from typing import Optional

class EditUserProfileRequest(BaseModel):
    name: Optional[str] = None 
    email: Optional[str] = None  
    password: Optional[str] = None  
    
