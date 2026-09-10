"""Web-first large-model entrypoint.

Keeps the verified engineering runtime intact while layering separate APIs for
viewer derivatives and the canonical XCAF assembly tree.
"""
from .app import app, workspace, ROOT
from .assembly_api import create_assembly_router
from .streaming_api import create_streaming_router

app.include_router(create_assembly_router(workspace))
app.include_router(create_streaming_router(workspace, ROOT))
