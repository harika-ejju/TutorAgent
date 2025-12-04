"""
WSGI module for gunicorn deployment
"""
import os
import sys

# Add current directory and backend to Python path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.join(current_dir, 'backend')

for path in [current_dir, backend_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Import the FastAPI application
from main import app

# WSGI application object
application = app