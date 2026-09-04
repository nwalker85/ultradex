-- 0000_prelude.sql
-- Extensions and shared helper functions for the CCC target schema.
-- Spec: docs/superpowers/specs/2026-08-31-career-crm-relational-schema-design.md
-- Amendment: docs/decisions/0002-ccc-scope-containment-model.md section 4

-- PG16 ships gen_random_uuid() in core, but pgcrypto is enabled for
-- portability with environments that still expect it explicitly.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- ccc_set_updated_at: generic BEFORE UPDATE trigger that stamps updated_at.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION ccc_set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION ccc_set_updated_at() IS
    'Schema conventions: maintains updated_at on tables that carry it.';

-- ---------------------------------------------------------------------------
-- ccc_reject_mutation: generic BEFORE UPDATE OR DELETE trigger that rejects
-- mutation of append-only tables (constraint 9 and related append-only rules
-- throughout sections 3, 4, 8, 9).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION ccc_reject_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'append-only table %.%: % is not permitted',
        TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'raise_exception';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION ccc_reject_mutation() IS
    'Constraint 9: enforces append-only tables by rejecting UPDATE and DELETE.';

-- ---------------------------------------------------------------------------
-- ccc_assert_same_workspace: helper for BEFORE INSERT/UPDATE triggers on link
-- tables the spec writes WITHOUT workspace_id (*_source_records, action_*).
-- Raises unless both endpoint rows' workspace_id values match.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION ccc_assert_same_workspace(ws_a uuid, ws_b uuid, label text)
RETURNS void AS $$
BEGIN
    IF ws_a IS NULL OR ws_b IS NULL OR ws_a <> ws_b THEN
        RAISE EXCEPTION 'cross-workspace association rejected for %: % <> %', label, ws_a, ws_b
            USING ERRCODE = 'raise_exception';
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION ccc_assert_same_workspace(uuid, uuid, text) IS
    'Constraint 13: workspace identity must match across every relationship; used by link-table triggers.';
