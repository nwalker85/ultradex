from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import uuid

import pytest


REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY / "scripts" / "create-obsidian-test-vault.sh"
VAULT = Path("/Users/nate/var/obsidian-test-vaults/ultradex-operator")
OBSIDIAN = VAULT / ".obsidian"
PLUGINS = OBSIDIAN / "plugins"
DESTINATION = PLUGINS / "ultradex-operator"
PLUGIN_SOURCE = REPOSITORY / "integrations" / "obsidian-ultradex"
BUILT_FILES = ("main.js", "manifest.json", "styles.css")
FIXED_VAULT_LITERAL = (
    "/Users/nate/var/obsidian-test-vaults/ultradex-operator"
)


def _run_installer(
    *arguments: str,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *arguments],
        cwd=REPOSITORY,
        env={**os.environ, **(environment or {})},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _ensure_synthetic_vault() -> None:
    PLUGINS.mkdir(parents=True, exist_ok=True)


def _copy_installer_with_fixed_temp_vault(
    tmp_path: Path,
    vault: Path,
) -> tuple[Path, dict[str, str]]:
    repository = tmp_path / "temporary-installer-repository"
    scripts = repository / "scripts"
    plugin_source = repository / "integrations" / "obsidian-ultradex"
    fake_bin = repository / "fake-bin"
    scripts.mkdir(parents=True)
    plugin_source.mkdir(parents=True)
    fake_bin.mkdir()

    original = SCRIPT.read_text()
    fixed_assignment = f'readonly vault="{FIXED_VAULT_LITERAL}"'
    assert original.count(fixed_assignment) == 1
    copied_script = scripts / SCRIPT.name
    copied_script.write_text(
        original.replace(
            fixed_assignment,
            f'readonly vault="{vault}"',
            1,
        )
    )
    copied_script.chmod(0o755)

    for name in BUILT_FILES:
        (plugin_source / name).write_bytes(f"synthetic-{name}\n".encode())

    fake_npm = fake_bin / "npm"
    fake_npm.write_text("#!/bin/sh\nexit 0\n")
    fake_npm.chmod(0o755)
    return copied_script, {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
    }


def test_installer_is_confined_to_the_fixed_synthetic_vault(
    tmp_path: Path,
) -> None:
    assert SCRIPT.is_file()
    _ensure_synthetic_vault()
    escaped_argument = tmp_path / "argument-escape"
    escaped_environment = tmp_path / "environment-escape"

    argument_result = _run_installer(str(escaped_argument))
    environment_result = _run_installer(
        environment={
            "ULTRADEX_OBSIDIAN_TEST_VAULT": str(escaped_environment),
        }
    )

    assert argument_result.returncode != 0
    assert environment_result.returncode != 0
    assert not escaped_argument.exists()
    assert not escaped_environment.exists()


@pytest.mark.parametrize("ancestor", ["early", "mid"])
def test_installer_refuses_symlinks_in_fixed_path_ancestors(
    tmp_path: Path,
    ancestor: str,
) -> None:
    destination_root = tmp_path / "destination-root"
    early = destination_root / "level-one"
    mid = early / "level-two"
    vault = mid / "ultradex-operator"
    trap = tmp_path / f"{ancestor}-ancestor-trap"
    if ancestor == "early":
        link = early
        suffix = Path("level-two") / "ultradex-operator"
    else:
        early.mkdir(parents=True)
        link = mid
        suffix = Path("ultradex-operator")
    (trap / suffix / ".obsidian" / "plugins").mkdir(parents=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(trap, target_is_directory=True)
    copied_script, environment = _copy_installer_with_fixed_temp_vault(
        tmp_path,
        vault,
    )
    before = sorted(path.relative_to(trap) for path in trap.rglob("*"))

    result = subprocess.run(
        [str(copied_script)],
        cwd=copied_script.parent.parent,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "symlink" in result.stderr
    assert sorted(path.relative_to(trap) for path in trap.rglob("*")) == before


@pytest.mark.parametrize(
    "component",
    [VAULT, OBSIDIAN, PLUGINS, DESTINATION],
    ids=["vault", "obsidian", "plugins", "plugin-destination"],
)
def test_installer_refuses_symlinked_path_components(component: Path) -> None:
    assert SCRIPT.is_file()
    _ensure_synthetic_vault()
    component.mkdir(exist_ok=True)
    suffix = uuid.uuid4().hex
    preserved = component.with_name(f"{component.name}.preserved-{suffix}")
    trap = component.with_name(f"{component.name}.symlink-trap-{suffix}")
    component.rename(preserved)
    trap.mkdir()
    component.symlink_to(trap, target_is_directory=True)
    try:
        result = _run_installer()
        assert result.returncode != 0
        assert list(trap.iterdir()) == []
    finally:
        component.unlink(missing_ok=True)
        preserved.rename(component)
        shutil.rmtree(trap)


def test_installer_preserves_local_state_and_copies_only_build_artifacts() -> None:
    assert SCRIPT.is_file()
    _ensure_synthetic_vault()
    DESTINATION.mkdir(exist_ok=True)
    data_file = DESTINATION / "data.json"
    community_plugins = OBSIDIAN / "community-plugins.json"
    data_contents = b'{"synthetic":"preserve-plugin-data"}\n'
    community_contents = b'["synthetic-existing-plugin"]\n'
    data_file.write_bytes(data_contents)
    community_plugins.write_bytes(community_contents)
    for name in BUILT_FILES:
        (DESTINATION / name).unlink(missing_ok=True)
    before = set(DESTINATION.iterdir())

    result = _run_installer()

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        str(DESTINATION),
        "Ultradex operator plugin installed successfully.",
    ]
    assert data_file.read_bytes() == data_contents
    assert community_plugins.read_bytes() == community_contents
    assert set(DESTINATION.iterdir()) - before == {
        DESTINATION / name for name in BUILT_FILES
    }
    for name in BUILT_FILES:
        source = PLUGIN_SOURCE / name
        installed = DESTINATION / name
        assert installed.read_bytes() == source.read_bytes()
        assert stat.S_IMODE(installed.stat().st_mode) == 0o644
