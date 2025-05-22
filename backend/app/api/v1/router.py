from fastapi import APIRouter
from backend.app.api.v1 import users, couples, accounts, goals, ledger, transactions, categories, plaid, budgets, rebalance, surplus, ai, forecast, allocation_rules, approvals
from backend.app.api.v1.journal import router as journal_router
from backend.app.api.v1.reactions import router as reactions_router
from backend.app.api.v1.timeline import router as timeline_router

api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(couples.router, prefix="/couples", tags=["couples"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(goals.router, prefix="/goals", tags=["goals"])
api_router.include_router(ledger.router, prefix="/ledger", tags=["ledger"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(plaid.router, prefix="/plaid", tags=["plaid"])
api_router.include_router(budgets.router, prefix="/budgets", tags=["budgets"])
api_router.include_router(rebalance.router, prefix="/rebalance", tags=["rebalance"])
api_router.include_router(surplus.router, prefix="/surplus", tags=["surplus"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(forecast.router, prefix="/forecast", tags=["forecast"])
api_router.include_router(allocation_rules.router, prefix="/allocation-rules", tags=["allocation-rules"])
api_router.include_router(journal_router, prefix="/journal", tags=["journal"])
api_router.include_router(reactions_router, prefix="/goals/reactions", tags=["reactions"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
api_router.include_router(timeline_router, prefix="/timeline", tags=["Timeline"])

# Uncomment these as you implement each module
# api_router.include_router(goals.router, prefix="/goals", tags=["goals"])