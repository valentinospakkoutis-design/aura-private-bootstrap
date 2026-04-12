"""Compatibility shim for Railway/uvicorn import paths.

This allows both of these startup forms to work:
- ``uvicorn main:app`` when cwd is ``backend``
- ``uvicorn backend.main:app`` when cwd is also ``backend``
"""

from main import app

