"""
PLG App — Configuration via environment variables.
Uses pydantic-settings for type-safe env var loading.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenRouter
    openrouter_api_key: str = Field(..., description="OpenRouter API key for Claude + Gemini")

    # LeadMagic
    leadmagic_api_key: str = Field(..., description="LeadMagic REST API key")

    # Google Sheets
    google_credentials_json: str = Field(..., description="Base64-encoded service account JSON")
    google_drive_folder_id: str = Field(..., description="Google Drive folder ID for sheets")

    # Instantly (optional — Make.com usually handles sending)
    instantly_api_key: str = Field(default="", description="Instantly API key (optional)")

    # App
    port: int = Field(default=8000, description="Server port")
    log_level: str = Field(default="INFO", description="Logging level")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
