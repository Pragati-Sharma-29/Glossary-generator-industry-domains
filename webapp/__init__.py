"""Web app package — FastAPI entry point re-exported for ``uvicorn webapp:app``."""
from .main import app

__all__ = ["app"]
