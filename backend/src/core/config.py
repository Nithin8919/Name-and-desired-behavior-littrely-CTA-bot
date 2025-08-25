from __future__ import annotations

import os
from typing import Optional
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application configuration settings."""
    
    # App settings
    app_name: str = "CTA Optimization Bot"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    
    # Server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # OpenAI settings
    openai_api_key: str = Field(env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4", env="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=2000, env="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.3, env="OPENAI_TEMPERATURE")
    
    # Scraping settings
    scraper_timeout: int = Field(default=30, env="SCRAPER_TIMEOUT")
    scraper_max_retries: int = Field(default=3, env="SCRAPER_MAX_RETRIES")
    scraper_delay: float = Field(default=1.0, env="SCRAPER_DELAY")
    max_pages_per_site: int = Field(default=10, env="MAX_PAGES_PER_SITE")
    max_crawl_depth: int = Field(default=2, env="MAX_CRAWL_DEPTH")
    
    # File upload settings
    max_file_size: int = Field(default=10 * 1024 * 1024, env="MAX_FILE_SIZE")  # 10MB
    upload_dir: str = Field(default="static/images", env="UPLOAD_DIR")
    screenshot_dir: str = Field(default="static/screenshots", env="SCREENSHOT_DIR")
    
    # OCR settings
    tesseract_path: Optional[str] = Field(default=None, env="TESSERACT_PATH")
    tesseract_lang: str = Field(default="eng", env="TESSERACT_LANG")
    
    # Redis settings (for caching and background tasks)
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    
    # Rate limiting
    rate_limit_calls: int = Field(default=100, env="RATE_LIMIT_CALLS")
    rate_limit_period: int = Field(default=3600, env="RATE_LIMIT_PERIOD")  # per hour
    
    # CORS settings
    allowed_origins: list[str] = Field(default=["*"], env="ALLOWED_ORIGINS")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
        env="LOG_FORMAT"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Create global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings


def setup_directories():
    """Create required directories if they don't exist."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.screenshot_dir, exist_ok=True)


# Setup logging
def setup_logging():
    """Configure logging for the application."""
    from loguru import logger
    import sys
    
    logger.remove()  # Remove default handler
    logger.add(
        sys.stdout,
        format=settings.log_format,
        level=settings.log_level,
        colorize=True
    )
    
    # Add file logging for production
    if not settings.debug:
        logger.add(
            "logs/app.log",
            format=settings.log_format,
            level=settings.log_level,
            rotation="1 day",
            retention="30 days"
        )
    
    return logger