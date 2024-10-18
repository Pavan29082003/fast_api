from  fastapi import FastAPI,APIRouter
import uvicorn
from src.auth import routes as auth_route
app = FastAPI()
# api_router = APIRouter()
app.include_router(auth_route.router,prefix="/auth")
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
