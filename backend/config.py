"""
Application settings loaded from environment variables / .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """Central configuration for the application."""

    # Paths
    PROJECT_ROOT: Path = PROJECT_ROOT
    DATA_DIR: Path = PROJECT_ROOT / "data"
    UPLOADS_DIR: Path = PROJECT_ROOT / "uploads" / "inspections"
    REPORTS_DIR: Path = PROJECT_ROOT / "reports"
    FRONTEND_DIR: Path = PROJECT_ROOT / "frontend"
    TEMPLATES_DIR: Path = Path(__file__).resolve().parent / "templates"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/car_inspection.db")

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "autoscan-pro-secret-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRY_MINUTES: int = int(os.getenv("JWT_EXPIRY_MINUTES", "480"))

    # SMTP
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # Company
    COMPANY_NAME: str = os.getenv("COMPANY_NAME", "AutoScan Pro")
    COMPANY_TAGLINE: str = os.getenv(
        "COMPANY_TAGLINE", "Professional Vehicle Inspection System"
    )

    # Server
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    def ensure_directories(self):
        """Create required directories if they don't exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self.REPORTS_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
