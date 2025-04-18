from fastapi import FastAPI
from backend.app.api.v1.router import api_router
from backend.app.database import create_tables

app = FastAPI(
    title="CFO Command Center",
    description="Financial coordination platform for couples",
    version="0.1.0"
)

# Include all API routes
app.include_router(api_router, prefix="/api/v1")

# Create DB tables on startup if they don't exist (for development)
@app.on_event("startup")
async def startup():
    create_tables()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)