from  fastapi import FastAPI,APIRouter
import uvicorn
from src.auth import routes as auth_route

from src.database import connections
from src.dashboard import create_user as dashboard_route



app = FastAPI()

app.include_router(auth_route.router,prefix="/auth")
app.include_router(dashboard_route.router,prefix="/user")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

