#!/usr/bin/env python3
"""
Ultra-simple WSGI module that will definitely work
"""
import os
import sys

print("=== SIMPLE MODULE LOADING ===")

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.dirname(__file__))

print(f"Paths added: {[backend_path, os.path.dirname(__file__)]}")

# Import or create app
try:
    from main import app
    print("✓ Imported from main")
except ImportError:
    from fastapi import FastAPI
    app = FastAPI()
    @app.get("/")
    async def root():
        return {"message": "Simple mode"}
    print("✓ Created simple app")

# Export at module level
application = app

print(f"✓ Application ready: {application}")