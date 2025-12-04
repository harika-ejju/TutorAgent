#!/usr/bin/env python3
"""
WSGI entry point for Render deployment.
Render looks for 'your_application.wsgi' by default.
"""
import os
import sys

# Add the backend directory to the Python path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Change working directory to backend
try:
    os.chdir(backend_dir)
except:
    pass

# Import the FastAPI app
from main import app

# This is what gunicorn expects
application = app

# For direct execution
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)