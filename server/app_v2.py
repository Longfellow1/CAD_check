"""Web-first large-model entrypoint.

Keeps the verified engineering runtime intact while layering a separate streaming view-derivative API.
"""
from .app import app, workspace, ROOT
from .streaming_api import create_streaming_router

app.include_router(create_streaming_router(workspace, ROOT))
