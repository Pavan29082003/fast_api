from  fastapi import FastAPI,APIRouter
import uvicorn
from src.auth import routes as auth_route
from src.notes import routes as notes_route
from src.rating import routes as rating_route
from src.bookmarks import routes as bookmarks_route
from fastapi.middleware.cors import CORSMiddleware
from src.history import routes as history_route
from src.database import connections
from src.dashboard import create_user as dashboard_route
from src.user import routes as user_routefrom src.core_search import routes as search_route

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_route.router,prefix="/auth")
app.include_router(dashboard_route.router,prefix="/admin")
app.include_router(user_route.router,prefix="/user")
app.include_router(notes_route.router,prefix="/notes")
app.include_router(rating_route.router,prefix="/rating")
app.include_router(bookmarks_route.router,prefix="/bookmarks")
app.include_router(history_route.router,prefix="/history")
app.include_router(search_route.router,prefix="/core_search")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

