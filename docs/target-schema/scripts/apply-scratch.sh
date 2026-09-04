#!/usr/bin/env bash
# apply-scratch.sh
# Creates a scratch PostgreSQL database, applies the CCC target-schema SQL
# files in lexical order (each schema file in its own transaction), runs the
# acceptance smoke test, prints a table count and the smoke summary, and
# drops the scratch database on success. On failure, the database is left in
# place and its name is printed so it can be inspected.

set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_DIR="$(cd "${SCRIPT_DIR}/../sql" && pwd)"

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
ADMIN_DB="${ADMIN_DB:-postgres}"

DB_NAME="ccc_target_scratch_$$"

echo "==> Creating scratch database: ${DB_NAME}"
if ! psql -h "${PGHOST}" -p "${PGPORT}" -d "${ADMIN_DB}" -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${DB_NAME};"; then
    echo "FAILED: could not create scratch database ${DB_NAME}"
    exit 1
fi

FAILED=0

# Schema files: each applied in its own transaction via --single-transaction.
# (Everything under sql/0*.sql except the 9000 acceptance script, in lexical order.)
SCHEMA_FILES=$(ls "${SQL_DIR}"/0*.sql | grep -v '/9000_smoke_roundtrip\.sql$' | sort)

for f in ${SCHEMA_FILES}; do
    [ -e "${f}" ] || continue
    echo "==> Applying $(basename "${f}")"
    if ! psql -h "${PGHOST}" -p "${PGPORT}" -d "${DB_NAME}" \
            -v ON_ERROR_STOP=1 --single-transaction \
            -f "${f}"; then
        echo "FAILED applying $(basename "${f}")"
        FAILED=1
        break
    fi
done

if [ "${FAILED}" -eq 0 ]; then
    SMOKE_FILE="${SQL_DIR}/9000_smoke_roundtrip.sql"
    echo "==> Running acceptance smoke test: $(basename "${SMOKE_FILE}")"
    if ! psql -h "${PGHOST}" -p "${PGPORT}" -d "${DB_NAME}" \
            -v ON_ERROR_STOP=1 \
            -f "${SMOKE_FILE}"; then
        echo "FAILED: smoke test did not complete cleanly"
        FAILED=1
    fi
fi

echo "==> Table count in ${DB_NAME}:"
psql -h "${PGHOST}" -p "${PGPORT}" -d "${DB_NAME}" -t -A -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"

if [ "${FAILED}" -eq 0 ]; then
    echo "==> Success. Dropping scratch database ${DB_NAME}."
    psql -h "${PGHOST}" -p "${PGPORT}" -d "${ADMIN_DB}" -v ON_ERROR_STOP=1 \
        -c "DROP DATABASE IF EXISTS ${DB_NAME};"
    echo "SCRATCH APPLY: OK (${DB_NAME} dropped)"
    exit 0
else
    echo "SCRATCH APPLY: FAILED (database kept: ${DB_NAME})"
    exit 1
fi
