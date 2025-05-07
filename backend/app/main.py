from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.app.api.v1.router import api_router
from backend.app.database import engine
from backend.app.models.models import Base

# WARNING: This will delete all data!
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code here
    print("Starting up application...")
    yield
    # Shutdown code here
    print("Shutting down application...")

app = FastAPI(lifespan=lifespan)

# Include all API routes
app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)