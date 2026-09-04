"""
Entrypoint in a location Vercel's FastAPI runtime looks in by default.

The application itself lives in churn_platform/main.py; re-exporting it here
lets Vercel build the ASGI app as a single function with a catch-all route
that preserves the request path, without a pyproject.toml (which would make
the build switch from requirements.txt to `uv lock`).

Running `uvicorn main:app` locally is equivalent to `uvicorn churn_platform.main:app`.
"""
from churn_platform.main import app

__all__ = ["app"]
