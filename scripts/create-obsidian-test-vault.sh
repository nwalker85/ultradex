#!/usr/bin/env bash

set -euo pipefail

readonly vault="/Users/nate/var/obsidian-test-vaults/ultradex-operator"
readonly obsidian="${vault}/.obsidian"
readonly plugins="${obsidian}/plugins"
readonly destination="${plugins}/ultradex-operator"
readonly override_names=(
  "OBSIDIAN_VAULT"
  "OBSIDIAN_VAULT_PATH"
  "OBSIDIAN_TEST_VAULT"
  "ULTRADEX_OBSIDIAN_TEST_VAULT"
  "ULTRADEX_OBSIDIAN_PLUGIN_DESTINATION"
)
readonly build_files=("main.js" "manifest.json" "styles.css")

fail() {
  printf 'Ultradex test-vault install refused: %s\n' "$1" >&2
  exit 1
}

reject_symlink_components() {
  local absolute_path="$1"
  local remaining
  local component
  local current=""

  if [[ "$absolute_path" != /* ]]; then
    fail "the fixed destination must be absolute"
  fi
  remaining="${absolute_path#/}"
  while [[ -n "$remaining" ]]; do
    if [[ "$remaining" == */* ]]; then
      component="${remaining%%/*}"
      remaining="${remaining#*/}"
    else
      component="$remaining"
      remaining=""
    fi
    if [[ -z "$component" ]]; then
      continue
    fi
    current="${current}/${component}"
    if [[ -L "$current" ]]; then
      fail "a fixed destination component is a symlink"
    fi
  done
}

if (( $# != 0 )); then
  fail "positional arguments are not accepted"
fi

for override_name in "${override_names[@]}"; do
  if [[ -n "${!override_name+x}" ]]; then
    fail "destination environment overrides are not accepted"
  fi
done

reject_symlink_components "$destination"

for required_directory in "$vault" "$obsidian" "$plugins"; do
  if [[ ! -d "$required_directory" ]]; then
    fail "the fixed synthetic vault must already contain .obsidian/plugins"
  fi
done

readonly repository="$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
  pwd -P
)"
readonly source_directory="${repository}/integrations/obsidian-ultradex"

build_ready=1
for build_file in "${build_files[@]}"; do
  if [[ ! -f "${source_directory}/${build_file}" ]]; then
    build_ready=0
    break
  fi
done

if (( build_ready == 0 )); then
  if ! command -v npm >/dev/null 2>&1; then
    fail "plugin build artifacts are missing and npm is unavailable"
  fi
  if ! (
    cd -- "$repository"
    npm run build --workspace obsidian-ultradex >/dev/null 2>&1
  ); then
    fail "the repository plugin build failed"
  fi
fi

# Recheck immediately before the first filesystem write after the build.
reject_symlink_components "$destination"

if [[ ! -e "$destination" ]]; then
  mkdir -- "$destination"
elif [[ ! -d "$destination" ]]; then
  fail "the fixed plugin destination is not a directory"
fi

for filename in "${build_files[@]}"; do
  source_file="${source_directory}/${filename}"
  installed_file="${destination}/${filename}"
  if [[ ! -f "$source_file" || -L "$source_file" ]]; then
    fail "a required repository build artifact is unavailable"
  fi
  if [[ -L "$installed_file" ]]; then
    fail "an installed artifact path is a symlink"
  fi
  reject_symlink_components "$destination"
  install -m 0644 -- "$source_file" "$installed_file"
  cmp -s -- "$source_file" "$installed_file" \
    || fail "an installed artifact failed byte verification"
done

printf '%s\n' "$destination"
printf 'Ultradex operator plugin installed successfully.\n'
