"""Public package surface for the Kling FastMCP server."""

from __future__ import annotations

from .server import create_server, main

__all__ = ["create_server", "main"]
