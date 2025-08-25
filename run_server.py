#!/usr/bin/env python3
"""
Production server runner for CTA Optimization Bot API.
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

import uvicorn
from loguru import logger

from src.core.config import get_settings, setup_logging, setup_directories


def main():
    """Main entry point for running the server."""
    
    # Setup logging and directories first
    setup_logging()
    setup_directories()
    
    logger.info("🚀 Starting CTA Optimization Bot API Server")
    
    # Get settings
    settings = get_settings()
    
    # Validate critical settings
    if not settings.openai_api_key:
        logger.error("❌ OPENAI_API_KEY environment variable is required!")
        logger.info("Please set your OpenAI API key: export OPENAI_API_KEY=your_key_here")
        sys.exit(1)
    
    logger.info(f"✅ Configuration loaded")
    logger.info(f"📊 Debug mode: {settings.debug}")
    logger.info(f"🔑 OpenAI API key configured: {len(settings.openai_api_key)} characters")
    logger.info(f"🌐 Server will start on: http://{settings.host}:{settings.port}")
    
    # Create required directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("exports", exist_ok=True)
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.screenshot_dir, exist_ok=True)
    
    # Configure uvicorn
    uvicorn_config = {
        "app": "src.main:app",
        "host": settings.host,
        "port": settings.port,
        "reload": settings.debug,
        "log_level": settings.log_level.lower(),
        "access_log": True,
    }
    
    # Add SSL configuration if in production
    if not settings.debug:
        uvicorn_config.update({
            "workers": 1,  # Single worker for now, can be increased
            "loop": "uvloop",  # Performance improvement
            "http": "httptools",  # Performance improvement
        })
    
    try:
        logger.info("🔥 Starting server with uvicorn...")
        uvicorn.run(**uvicorn_config)
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"💥 Server failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()