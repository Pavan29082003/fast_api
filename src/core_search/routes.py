from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from fastapi.middleware.cors import CORSMiddleware
from src.core_search import utils
from fastapi import APIRouter, Depends, HTTPException, status
from sentence_transformers import SentenceTransformer
from src.core_search.models import *

router = APIRouter()

@router.get("/")
async def get_results(
        request: Request,
        term: str,
        article_type: Optional[str] = None,
        date_filter: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        source: Optional[str] = None
    ):

    response = utils.get_data(request.query_params)

    return JSONResponse(
        status_code=status.HTTP_200_OK, content={"articles": list(response)}
    )

@router.post("/annotate")
async def annotate( request: AnnotateRequest ):
    response = await utils.annotate(pubmed=request.pubmed, biorxiv=request.biorxiv, plos=request.plos)
    print(response)
    response = utils.annotation_score(response)

    return JSONResponse(
        status_code=status.HTTP_200_OK, content=response 
    )



