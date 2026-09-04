"""
Vercel serverless entrypoint.

Vercel imports `app` from this module and serves it with the Python runtime;
`vercel.json` rewrites every path here so FastAPI does its own routing.
"""
import sys
from pathlib import Path

# The function runs from the repository root, but make the import explicit so
# the package resolves regardless of how the runtime sets sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from churn_platform.main import app  # noqa: E402

__all__ = ["app"]
