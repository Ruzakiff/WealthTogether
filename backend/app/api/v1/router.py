from fastapi import APIRouter
from backend.app.api.v1 import users, couples

api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(couples.router, prefix="/couples", tags=["couples"])

# Uncomment these as you implement each module
# api_router.include_router(goals.router, prefix="/goals", tags=["goals"])
# api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])