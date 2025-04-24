from fastapi import APIRouter
from backend.app.api.v1 import users, couples, accounts, goals, ledger, transactions, categories, plaid

api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(couples.router, prefix="/couples", tags=["couples"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(goals.router, prefix="/goals", tags=["goals"])
api_router.include_router(ledger.router, prefix="/ledger", tags=["ledger"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(plaid.router, prefix="/plaid", tags=["plaid"])

# Uncomment these as you implement each module
# api_router.include_router(goals.router, prefix="/goals", tags=["goals"])