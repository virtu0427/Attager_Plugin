"""Entry point so Uvicorn can import `app.main:app`."""
from jws import app


__all__ = ["app"]
