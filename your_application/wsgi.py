import os
import sys

# Add the backend directory to the Python path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import the FastAPI app
from main import app

# This is what gunicorn expects
application = app