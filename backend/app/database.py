import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# You may want to use environment variables for this in production
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cfo_command_center.db")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables in the database
def create_tables():
    from backend.app.models.models import Base
    Base.metadata.create_all(bind=engine)

# Dependency to get the database session
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
