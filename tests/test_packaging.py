from __future__ import annotations

import pathlib
import subprocess
import sys
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_built_wheel_contains_only_the_official_sdk_package(tmp_path):
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
    assert not any(path.startswith("mcp/") for path in paths)
    assert not any(path.startswith("cli/") for path in paths)
