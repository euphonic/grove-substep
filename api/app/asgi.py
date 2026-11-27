"""Server entry point: `fastapi dev app/asgi.py`.

Kept separate from app.main so importing the app factory (tests, scripts, evals) never
builds settings at import time.
"""

from app.main import create_app

app = create_app()
