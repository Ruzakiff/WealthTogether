from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Database settings
    database_url: str = "sqlite:///./app.db"
    
    # Plaid API settings
    plaid_client_id: str = "6806ec46a85369001fbdd150"
    plaid_secret: str = "0130fba01eff066fa9b8a48802e88b"
    plaid_environment: str = "https://sandbox.plaid.com"  # Use sandbox for development
    
    # Other settings...
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
