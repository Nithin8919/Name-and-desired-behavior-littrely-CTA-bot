# backend/app.py - Complete integrated server
import os
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add backend src to path
backend_dir = Path(__file__).parent
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))

# Import backend modules
try:
    from src.api.endpoints import router as api_router
    from src.core.config import get_settings, setup_directories, setup_logging
    from src.main import create_app
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the backend directory and all dependencies are installed")
    sys.exit(1)

def create_integrated_app():
    """Create integrated FastAPI app with frontend serving."""
    
    # Get settings
    settings = get_settings()
    
    # Setup directories and logging
    setup_directories()
    setup_logging()
    
    # Create FastAPI app
    app = FastAPI(
        title="CTA Optimization Bot",
        version="1.0.0",
        description="AI-powered CTA optimization with integrated frontend"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routes
    app.include_router(api_router, prefix="/api/v1", tags=["CTA Analysis"])
    
    # Serve static files
    static_dir = backend_dir / "static"
    static_dir.mkdir(exist_ok=True)
    
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Frontend route
    @app.get("/", response_class=HTMLResponse)
    async def serve_frontend():
        """Serve the frontend HTML."""
        frontend_file = static_dir / "index.html"
        
        if not frontend_file.exists():
            # Return instructions if frontend file doesn't exist
            return HTMLResponse("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>CTA Optimization Bot - Setup Required</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
                    .setup-box { background: #f0f8ff; border: 1px solid #0066cc; border-radius: 8px; padding: 20px; }
                    .step { background: white; margin: 10px 0; padding: 15px; border-radius: 5px; border-left: 4px solid #0066cc; }
                    code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }
                </style>
            </head>
            <body>
                <h1>🚀 CTA Optimization Bot Setup</h1>
                <div class="setup-box">
                    <h2>Frontend Setup Required</h2>
                    <p>To complete the setup, please save the professional frontend code to:</p>
                    <code>backend/static/index.html</code>
                    
                    <div class="step">
                        <h3>Step 1: Create the file</h3>
                        <p>Create <code>backend/static/index.html</code> and paste the frontend code provided.</p>
                    </div>
                    
                    <div class="step">
                        <h3>Step 2: Set OpenAI API Key</h3>
                        <p>Set your OpenAI API key as an environment variable:</p>
                        <code>export OPENAI_API_KEY=your_api_key_here</code>
                    </div>
                    
                    <div class="step">
                        <h3>Step 3: Refresh this page</h3>
                        <p>Once you've completed steps 1-2, refresh this page to see the CTA Optimizer interface.</p>
                    </div>
                </div>
                
                <h2>API Status</h2>
                <p>✅ Backend API is running</p>
                <p>📖 API Documentation: <a href="/docs">http://localhost:8000/docs</a></p>
                <p>🔍 Health Check: <a href="/api/v1/health">http://localhost:8000/api/v1/health</a></p>
            </body>
            </html>
            """)
        
        return FileResponse(frontend_file)
    
    # Health check
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "CTA Optimization Bot"}
    
    return app

if __name__ == "__main__":
    # Validate OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OpenAI API Key Required")
        print("Please set your OpenAI API key:")
        print("export OPENAI_API_KEY=sk-your-key-here")
        print()
        sys.exit(1)
    
    # Create app
    app = create_integrated_app()
    
    print("🚀 Starting CTA Optimization Bot")
    print("📱 Frontend: http://localhost:8000")
    print("📖 API Docs: http://localhost:8000/docs")
    print("🔑 OpenAI API Key: ✅ Configured")
    print()
    print("Waiting for requests...")
    
    # Run server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(backend_dir)]
    )