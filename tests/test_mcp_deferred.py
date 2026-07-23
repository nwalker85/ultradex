from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.xfail(
    reason="JS-U06 owns the top-level mcp package collision and runtime integration",
    strict=True,
)
def test_mcp_runtime_import_is_deferred_but_visible():
    result = subprocess.run(
        [sys.executable, "-c", "from mcp import UltradexMCPServer"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
