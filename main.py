from  fastapi import FastAPI,APIRouter
import uvicorn
from src.auth import routes as auth_route
from src.notes import routes as notes_route
from src.rating import routes as rating_route

app = FastAPI()
# api_router = APIRouter()
app.include_router(auth_route.router,prefix="/auth")
app.include_router(notes_route.router,prefix="/notes")
app.include_router(rating_route.router,prefix="/rating")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

