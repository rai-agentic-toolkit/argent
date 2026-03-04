"""Shared pytest fixtures for Argent test suite."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def payloads_dir(fixtures_dir: Path) -> Path:
    """Return the path to the payload fixtures directory."""
    return fixtures_dir / "payloads"


@pytest.fixture
def oversized_json_payload() -> bytes:
    """Generate a large JSON payload (~2MB) for pre-allocation limit tests.

    Generated at test time rather than committed to avoid the 1MB file-size
    gate on large binary/text assets in pre-commit hooks.
    """
    records = [{"id": i, "tool": "search_cve", "args": {"query": "A" * 200}} for i in range(5000)]
    return json.dumps(records).encode()
