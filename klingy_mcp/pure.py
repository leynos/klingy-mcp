"""Provide the pure-Python fallback when the Rust extension is unavailable."""

from __future__ import annotations


def hello() -> str:
    """Return a friendly greeting from Python."""
    return "hello from Python"
