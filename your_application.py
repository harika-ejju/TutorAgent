#!/usr/bin/env python3
"""
Main application module that Render's gunicorn can find.
"""
import os
import sys

# Add the backend directory to the Python path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import the FastAPI app
try:
    from main import app
    application = app
except ImportError as e:
    print(f"Error importing main: {e}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    raise

# Create a wsgi attribute for gunicorn
wsgi = type('wsgi', (), {'application': application})()

# For direct execution
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(application, host="0.0.0.0", port=port)