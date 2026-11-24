"""Tests for the pure-Python fallback greeting."""

from __future__ import annotations

from klingy_mcp.pure import hello


def test_hello_returns_the_python_greeting() -> None:
    """The fallback greeting names Python as its source."""
    assert hello() == "hello from Python"
