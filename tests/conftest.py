import pytest


@pytest.fixture(autouse=True)
def clear_scans():
    """Reset the in-memory scan registry before each test."""
    from server import _scans
    _scans.clear()
    yield
    _scans.clear()
