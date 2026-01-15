"""
Application configuration using Pydantic Settings.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "Orbit"
    debug: bool = False
    secret_key: str = "change-this-in-production"
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./orbit.db"
    
    # JWT
    jwt_secret_key: str = "change-this-jwt-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/integrations/google/callback"
    
    # Slack OAuth
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_redirect_uri: str = "http://localhost:8000/api/v1/integrations/slack/callback"
    
    # Notion OAuth
    notion_client_id: str = ""
    notion_client_secret: str = ""
    notion_redirect_uri: str = "http://localhost:8000/api/v1/integrations/notion/callback"
    
    # Stripe
    stripe_api_key: str = ""
    
    # Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-3-5-sonnet-20241022"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
