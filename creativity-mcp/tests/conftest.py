"""Test configuration for creativity-mcp."""
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear sessions before each test."""
    from creativity_mcp.server import sessions
    sessions.clear()
    yield
    sessions.clear()
