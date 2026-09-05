"""
Vercel Python runtime entry point for PaperBlast FastAPI backend.

P0 FIX: Replaces the broken api/index.js → server/index.js Node adapter.
This file is the actual Vercel serverless function handler that wraps the
FastAPI ASGI application defined in server/main.py.

Vercel routes:  /api/(*) → this file (via vercel.json functions config)
"""
import sys
import os

# Ensure the project root is on the Python path so server.* imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from server.main import app  # FastAPI ASGI application

# Vercel Python runtime expects a module-level `app` or `handler` variable.
# The FastAPI `app` is an ASGI-compatible callable — Vercel wraps it automatically.
handler = app
