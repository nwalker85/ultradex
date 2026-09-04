-- 0006_provenance.sql
-- Spec section 8 "Integration provenance".
-- Constraint 11: an integration-account deletion cannot cascade-delete
-- organizations, contacts, leads, opportunities, interactions, or documents.
-- Achieved structurally: none of those tables carry any FK to
-- integration_accounts, and every FK in this file defaults to RESTRICT
-- (schema convention), so no ON DELETE CASCADE path exists from
-- integration_accounts into pursuit state or identity projections.

-- ---------------------------------------------------------------------------
-- integration_accounts
-- ---------------------------------------------------------------------------
CREATE TABLE integration_accounts (
    id                              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id                    uuid NOT NULL REFERENCES workspaces (id),
    provider                        text NOT NULL,
    external_account_ref            text NOT NULL,
    external_account_commitment     text NOT NULL,
    status                          text NOT NULL,
    last_synced_at                  timestamptz NULL,
    created_at                      timestamptz NOT NULL DEFAULT now(),
    updated_at                      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT integration_accounts_workspace_provider_commitment_uq
        UNIQUE (workspace_id, provider, external_account_commitment),
    CONSTRAINT integration_accounts_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE integration_accounts IS
    'Spec section 8: a connected external provider account, keyed by opaque commitment.';

CREATE TRIGGER trg_integration_accounts_updated_at
    BEFORE UPDATE ON integration_accounts
    FOR EACH ROW EXECUTE FUNCTION ccc_set_updated_at();

-- ---------------------------------------------------------------------------
-- sync_runs
-- ---------------------------------------------------------------------------
CREATE TABLE sync_runs (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id             uuid NOT NULL REFERENCES workspaces (id),
    integration_account_id   uuid NOT NULL,
    started_at               timestamptz NOT NULL,
    completed_at             timestamptz NULL,
    status                   text NOT NULL,
    cursor_ref               text NULL,
    records_seen             integer NOT NULL DEFAULT 0,
    records_created          integer NOT NULL DEFAULT 0,
    records_updated          integer NOT NULL DEFAULT 0,
    redacted_error_summary   text NULL,

    CONSTRAINT sync_runs_account_fk
        FOREIGN KEY (workspace_id, integration_account_id)
        REFERENCES integration_accounts (workspace_id, id)
);

COMMENT ON TABLE sync_runs IS
    'Spec section 8: one execution of an integration sync against an integration account.';

-- ---------------------------------------------------------------------------
-- source_records
-- ---------------------------------------------------------------------------
CREATE TABLE source_records (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id             uuid NOT NULL REFERENCES workspaces (id),
    integration_account_id   uuid NOT NULL,
    object_type              text NOT NULL,
    external_object_ref      text NOT NULL,
    external_id_commitment   text NOT NULL,
    first_seen_at            timestamptz NOT NULL,
    last_seen_at             timestamptz NOT NULL,

    CONSTRAINT source_records_account_fk
        FOREIGN KEY (workspace_id, integration_account_id)
        REFERENCES integration_accounts (workspace_id, id),
    CONSTRAINT source_records_account_type_commitment_uq
        UNIQUE (integration_account_id, object_type, external_id_commitment),
    CONSTRAINT source_records_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE source_records IS
    'Spec section 8: a discovered external object, keyed by opaque commitment within its integration account.';

-- ---------------------------------------------------------------------------
-- source_record_versions (append-only; trigger added in 0011)
-- ---------------------------------------------------------------------------
CREATE TABLE source_record_versions (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id           uuid NOT NULL REFERENCES workspaces (id),
    source_record_id       uuid NOT NULL,
    content_ref            text NULL,
    content_commitment     text NULL,
    normalized_metadata    jsonb NOT NULL DEFAULT '{}',
    content_fingerprint    text NOT NULL,
    observed_at            timestamptz NOT NULL,

    CONSTRAINT source_record_versions_record_fk
        FOREIGN KEY (workspace_id, source_record_id)
        REFERENCES source_records (workspace_id, id),
    CONSTRAINT source_record_versions_record_fingerprint_uq
        UNIQUE (source_record_id, content_fingerprint)
);

COMMENT ON TABLE source_record_versions IS
    'Spec section 8 + constraint 9: append-only observed version of a source record.';

-- ---------------------------------------------------------------------------
-- Typed provenance links. The spec writes these WITHOUT workspace_id; a
-- BEFORE INSERT/UPDATE trigger (added in 0011) asserts both endpoints share a
-- workspace (constraint 13), since a plain composite FK is not available
-- without a local workspace_id column.
-- ---------------------------------------------------------------------------
CREATE TABLE organization_source_records (
    organization_id     uuid NOT NULL REFERENCES organizations (id),
    source_record_id    uuid NOT NULL REFERENCES source_records (id),

    PRIMARY KEY (organization_id, source_record_id)
);

COMMENT ON TABLE organization_source_records IS
    'Spec section 8: typed provenance link from an organization projection to its source record(s).';

CREATE TABLE contact_source_records (
    contact_id           uuid NOT NULL REFERENCES contacts (id),
    source_record_id     uuid NOT NULL REFERENCES source_records (id),

    PRIMARY KEY (contact_id, source_record_id)
);

COMMENT ON TABLE contact_source_records IS
    'Spec section 8: typed provenance link from a contact projection to its source record(s).';

CREATE TABLE lead_source_records (
    lead_id              uuid NOT NULL,
    source_record_id     uuid NOT NULL REFERENCES source_records (id),

    PRIMARY KEY (lead_id, source_record_id)
);

COMMENT ON TABLE lead_source_records IS
    'Spec section 8: typed provenance link from a lead to its source record(s).';

CREATE TABLE interaction_source_records (
    interaction_id       uuid NOT NULL REFERENCES interactions (id),
    source_record_id     uuid NOT NULL REFERENCES source_records (id),

    PRIMARY KEY (interaction_id, source_record_id)
);

COMMENT ON TABLE interaction_source_records IS
    'Spec section 8: typed provenance link from an interaction to its source record(s).';

CREATE TABLE opportunity_source_records (
    opportunity_id        uuid NOT NULL REFERENCES opportunities (id),
    source_record_id      uuid NOT NULL REFERENCES source_records (id),

    PRIMARY KEY (opportunity_id, source_record_id)
);

COMMENT ON TABLE opportunity_source_records IS
    'Spec section 8: typed provenance link from an opportunity to its source record(s).';
