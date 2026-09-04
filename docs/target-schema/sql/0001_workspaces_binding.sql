-- 0001_workspaces_binding.sql
-- Spec section 1 "Workspace ownership", amended per ADR-0002 section 4:
-- workspace_tenant_binding_projection -> workspace_scope_binding_projection
-- with added organization_id/application_id/project_id/scope_key columns.

CREATE TABLE workspaces (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE workspaces IS
    'Spec section 1: every user-owned record belongs to exactly one workspace.';

CREATE TRIGGER trg_workspaces_updated_at
    BEFORE UPDATE ON workspaces
    FOR EACH ROW EXECUTE FUNCTION ccc_set_updated_at();

-- ---------------------------------------------------------------------------
-- workspace_scope_binding_projection
-- Renamed from workspace_tenant_binding_projection by ADR-0002 section 4.
-- Only the Mimir binding resolver refreshes this projection through a
-- governed event/SDK path (spec section 1). CCC never writes it locally.
-- ---------------------------------------------------------------------------
CREATE TABLE workspace_scope_binding_projection (
    workspace_id        uuid PRIMARY KEY REFERENCES workspaces (id),
    projection_status   text NOT NULL,
    tenant_id           text NULL,
    organization_id      text NULL,
    application_id       text NULL,
    project_id           text NULL,
    scope_key            text NULL,
    mapping_version      text NULL,
    registry_revision    text NOT NULL,
    resolver_version     text NOT NULL,
    lineage_ref          text NOT NULL,
    effective_at         timestamptz NULL,
    resolved_at          timestamptz NOT NULL,
    expires_at           timestamptz NOT NULL,
    freshness            text NOT NULL,

    CONSTRAINT workspace_scope_binding_projection_status_chk
        CHECK (projection_status IN ('resolved', 'unavailable', 'conflict')),
    CONSTRAINT workspace_scope_binding_projection_freshness_chk
        CHECK (freshness IN ('current', 'stale')),

    -- Spec section 1 + ADR-0002 section 4: tenant_id, mapping_version,
    -- effective_at are present exactly when resolved; ADR-0002 applies the
    -- same rule to organization_id, application_id, project_id, scope_key.
    CONSTRAINT workspace_scope_binding_projection_resolved_fields_chk
        CHECK (
            (projection_status = 'resolved'
                AND tenant_id IS NOT NULL
                AND organization_id IS NOT NULL
                AND application_id IS NOT NULL
                AND project_id IS NOT NULL
                AND scope_key IS NOT NULL
                AND mapping_version IS NOT NULL
                AND effective_at IS NOT NULL)
            OR
            (projection_status <> 'resolved'
                AND tenant_id IS NULL
                AND organization_id IS NULL
                AND application_id IS NULL
                AND project_id IS NULL
                AND scope_key IS NULL
                AND mapping_version IS NULL
                AND effective_at IS NULL)
        )
);

COMMENT ON TABLE workspace_scope_binding_projection IS
    'Spec section 1 + ADR-0002 section 4: Mimir-owned workspace-to-scope binding cache; CCC never writes it locally.';
