from __future__ import annotations

import pathlib
import os
import subprocess
import sys
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_built_wheel_preserves_sdk_compatibility_without_server_packages(tmp_path):
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(tmp_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = tuple(tmp_path.glob("ultradex_sdk-*.whl"))
    assert len(wheels) == 1

    with zipfile.ZipFile(wheels[0]) as archive:
        paths = set(archive.namelist())

    assert "ultradex_sdk/__init__.py" in paths
    assert "ultradex_sdk/ultradex_sdk.py" in paths
    assert "sdk/__init__.py" in paths
    assert "sdk/ultradex_sdk.py" in paths
    assert "sdk/py.typed" in paths
    assert not any(path.startswith("mcp/") for path in paths)
    assert not any(path.startswith("cli/") for path in paths)

    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(wheels[0]) as archive:
        archive.extractall(extracted)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(extracted)
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from sdk import UltradexClient as Legacy; "
                "from ultradex_sdk import UltradexClient as Current; "
                "assert Legacy is Current"
            ),
        ],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
