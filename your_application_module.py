#!/usr/bin/env python3
"""
Main application module that Render's gunicorn can find.
"""
import os
import sys

# Globals that will be available at module level
application = None
wsgi = None

# Print debug info for deployment troubleshooting
print(f"=== Loading your_application.py ===")
print(f"File location: {__file__}")
print(f"Working directory: {os.getcwd()}")
print(f"Directory contents: {os.listdir('.')}")

# Add the backend directory to the Python path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
    print(f"Added to Python path: {backend_dir}")

print(f"Final Python path: {sys.path}")

# Import the FastAPI app with fallback
try:
    print("Attempting to import from main...")
    from main import app
    print("✓ Successfully imported FastAPI app from main")
    application = app
except ImportError as e:
    print(f"✗ Error importing main: {e}")
    print("Creating fallback FastAPI application...")
    
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    
    app = FastAPI(title="Tutor Agent API (Fallback)", version="1.0.0")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "message": "Tutor Agent API running in fallback mode"}
    
    application = app
    print("✓ Created fallback FastAPI application")

# Create a wsgi attribute for gunicorn
wsgi = type('wsgi', (), {'application': application})()
print(f"✓ Created WSGI wrapper, application type: {type(application)}")

# Verify module-level access
print(f"Module-level application: {application}")
print(f"Module-level wsgi: {wsgi}")

# For direct execution
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting server directly on port {port}")
    uvicorn.run(application, host="0.0.0.0", port=port)
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting server directly on port {port}")
    uvicorn.run(application, host="0.0.0.0", port=port)