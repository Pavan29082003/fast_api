from typing import List, Optional
from pydantic import BaseModel

class AnnotateRequest(BaseModel):
    pubmed: Optional[List[int]] = None
    biorxiv: Optional[List[int]] = None
    plos: Optional[List[int]] = None
