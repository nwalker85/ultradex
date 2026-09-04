-- 0002_identity_projections.sql
-- Spec section 2 "Organizations and contacts", amended per ADR-0002 section 4
-- (mimir_scope_key added to organizations and contacts).

-- ---------------------------------------------------------------------------
-- organizations
-- ---------------------------------------------------------------------------
CREATE TABLE organizations (
    id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id              uuid NOT NULL REFERENCES workspaces (id),
    mimir_entity_id           text NULL,
    resolution_status         text NOT NULL,
    resolution_id             text NULL,
    mimir_entity_version      integer NULL,
    tenant_mapping_version    text NULL,
    registry_revision         text NULL,
    resolver_version          text NULL,
    policy_version            text NULL,
    resolution_lineage_ref    text NULL,
    source_event_position     text NULL,
    resolution_expires_at     timestamptz NULL,
    resolution_freshness      text NULL,
    mimir_scope_key           text NULL,
    display_name              text NOT NULL,
    kind                      text NOT NULL,
    website_url               text NULL,
    linkedin_url              text NULL,
    redacted_summary          text NULL,
    resolved_at               timestamptz NULL,
    created_at                timestamptz NOT NULL DEFAULT now(),
    updated_at                timestamptz NOT NULL DEFAULT now(),
    deleted_at                timestamptz NULL,

    CONSTRAINT organizations_resolution_status_chk
        CHECK (resolution_status IN ('unresolved', 'resolved', 'ambiguous', 'disputed', 'retired')),
    CONSTRAINT organizations_kind_chk
        CHECK (kind IN ('company', 'nonprofit', 'government', 'school', 'association', 'other')),
    CONSTRAINT organizations_resolution_freshness_chk
        CHECK (resolution_freshness IS NULL OR resolution_freshness IN ('current', 'stale')),

    -- Spec section 2 + constraint 15: resolved requires a full coordinate and
    -- resolution provenance, and resolution_freshness = current.
    CONSTRAINT organizations_resolved_fields_chk
        CHECK (
            resolution_status <> 'resolved'
            OR (
                mimir_entity_id IS NOT NULL
                AND resolution_id IS NOT NULL
                AND mimir_entity_version IS NOT NULL
                AND tenant_mapping_version IS NOT NULL
                AND registry_revision IS NOT NULL
                AND resolver_version IS NOT NULL
                AND policy_version IS NOT NULL
                AND resolution_lineage_ref IS NOT NULL
                AND source_event_position IS NOT NULL
                AND resolution_expires_at IS NOT NULL
                AND resolved_at IS NOT NULL
                AND resolution_freshness = 'current'
                AND mimir_scope_key IS NOT NULL
            )
        ),
    -- Spec section 2: unresolved and ambiguous require a null coordinate.
    -- ADR-0002 applies the same presence rule to mimir_scope_key.
    CONSTRAINT organizations_unresolved_null_coordinate_chk
        CHECK (
            resolution_status NOT IN ('unresolved', 'ambiguous')
            OR (mimir_entity_id IS NULL AND mimir_scope_key IS NULL)
        ),

    CONSTRAINT organizations_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE organizations IS
    'Spec section 2 + ADR-0002 section 4: workspace-local organization projection; Mimir is the identity authority.';

CREATE TRIGGER trg_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION ccc_set_updated_at();

-- Spec section 2: "A resolved projection is unique by (workspace_id, mimir_entity_id)."
CREATE UNIQUE INDEX organizations_workspace_mimir_entity_uidx
    ON organizations (workspace_id, mimir_entity_id)
    WHERE mimir_entity_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- organization_domains
-- ---------------------------------------------------------------------------
CREATE TABLE organization_domains (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       uuid NOT NULL REFERENCES workspaces (id),
    organization_id    uuid NOT NULL,
    domain             text NOT NULL,
    normalized_domain  text NOT NULL,
    is_primary         boolean NOT NULL DEFAULT false,

    CONSTRAINT organization_domains_org_fk
        FOREIGN KEY (workspace_id, organization_id)
        REFERENCES organizations (workspace_id, id),
    CONSTRAINT organization_domains_workspace_normdomain_uq
        UNIQUE (workspace_id, normalized_domain)
);

COMMENT ON TABLE organization_domains IS
    'Spec section 2: cached public domains for an organization projection.';

-- ---------------------------------------------------------------------------
-- organization_aliases
-- ---------------------------------------------------------------------------
CREATE TABLE organization_aliases (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       uuid NOT NULL REFERENCES workspaces (id),
    organization_id    uuid NOT NULL,
    alias              text NOT NULL,
    normalized_alias   text NOT NULL,

    CONSTRAINT organization_aliases_org_fk
        FOREIGN KEY (workspace_id, organization_id)
        REFERENCES organizations (workspace_id, id),
    CONSTRAINT organization_aliases_org_normalias_uq
        UNIQUE (organization_id, normalized_alias)
);

COMMENT ON TABLE organization_aliases IS
    'Spec section 2: cached aliases for an organization projection.';

-- ---------------------------------------------------------------------------
-- contacts
-- ---------------------------------------------------------------------------
CREATE TABLE contacts (
    id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id              uuid NOT NULL REFERENCES workspaces (id),
    mimir_entity_id           text NULL,
    resolution_status         text NOT NULL,
    resolution_id             text NULL,
    mimir_entity_version      integer NULL,
    tenant_mapping_version    text NULL,
    registry_revision         text NULL,
    resolver_version          text NULL,
    policy_version            text NULL,
    resolution_lineage_ref    text NULL,
    source_event_position     text NULL,
    resolution_expires_at     timestamptz NULL,
    resolution_freshness      text NULL,
    mimir_scope_key           text NULL,
    display_name              text NOT NULL,
    headline                  text NULL,
    redacted_summary          text NULL,
    resolved_at               timestamptz NULL,
    created_at                timestamptz NOT NULL DEFAULT now(),
    updated_at                timestamptz NOT NULL DEFAULT now(),
    deleted_at                timestamptz NULL,

    CONSTRAINT contacts_resolution_status_chk
        CHECK (resolution_status IN ('unresolved', 'resolved', 'ambiguous', 'disputed', 'retired')),
    CONSTRAINT contacts_resolution_freshness_chk
        CHECK (resolution_freshness IS NULL OR resolution_freshness IN ('current', 'stale')),

    CONSTRAINT contacts_resolved_fields_chk
        CHECK (
            resolution_status <> 'resolved'
            OR (
                mimir_entity_id IS NOT NULL
                AND resolution_id IS NOT NULL
                AND mimir_entity_version IS NOT NULL
                AND tenant_mapping_version IS NOT NULL
                AND registry_revision IS NOT NULL
                AND resolver_version IS NOT NULL
                AND policy_version IS NOT NULL
                AND resolution_lineage_ref IS NOT NULL
                AND source_event_position IS NOT NULL
                AND resolution_expires_at IS NOT NULL
                AND resolved_at IS NOT NULL
                AND resolution_freshness = 'current'
                AND mimir_scope_key IS NOT NULL
            )
        ),
    CONSTRAINT contacts_unresolved_null_coordinate_chk
        CHECK (
            resolution_status NOT IN ('unresolved', 'ambiguous')
            OR (mimir_entity_id IS NULL AND mimir_scope_key IS NULL)
        ),

    CONSTRAINT contacts_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE contacts IS
    'Spec section 2 + ADR-0002 section 4: workspace-local contact projection; Mimir is the identity authority.';

CREATE TRIGGER trg_contacts_updated_at
    BEFORE UPDATE ON contacts
    FOR EACH ROW EXECUTE FUNCTION ccc_set_updated_at();

-- Spec section 2: "A resolved contact projection is unique by (workspace_id, mimir_entity_id)."
CREATE UNIQUE INDEX contacts_workspace_mimir_entity_uidx
    ON contacts (workspace_id, mimir_entity_id)
    WHERE mimir_entity_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- contact_channels
-- ---------------------------------------------------------------------------
CREATE TABLE contact_channels (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       uuid NOT NULL REFERENCES workspaces (id),
    contact_id         uuid NOT NULL,
    channel_type       text NOT NULL,
    channel_ref        text NOT NULL,
    value_commitment   text NOT NULL,
    display_hint       text NULL,
    is_primary         boolean NOT NULL DEFAULT false,

    CONSTRAINT contact_channels_contact_fk
        FOREIGN KEY (workspace_id, contact_id)
        REFERENCES contacts (workspace_id, id),
    CONSTRAINT contact_channels_type_chk
        CHECK (channel_type IN ('email', 'phone', 'linkedin')),
    CONSTRAINT contact_channels_workspace_type_commitment_uq
        UNIQUE (workspace_id, channel_type, value_commitment)
);

COMMENT ON TABLE contact_channels IS
    'Spec section 2: opaque, commitment-bound contact channels; raw values stay in connector custody.';

-- ---------------------------------------------------------------------------
-- contact_organization_affiliations
-- ---------------------------------------------------------------------------
CREATE TABLE contact_organization_affiliations (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       uuid NOT NULL REFERENCES workspaces (id),
    contact_id         uuid NOT NULL,
    organization_id    uuid NOT NULL,
    title              text NULL,
    department         text NULL,
    started_at         date NULL,
    ended_at           date NULL,
    is_current         boolean NOT NULL DEFAULT true,

    CONSTRAINT contact_org_affiliations_contact_fk
        FOREIGN KEY (workspace_id, contact_id)
        REFERENCES contacts (workspace_id, id),
    CONSTRAINT contact_org_affiliations_org_fk
        FOREIGN KEY (workspace_id, organization_id)
        REFERENCES organizations (workspace_id, id)
);

COMMENT ON TABLE contact_organization_affiliations IS
    'Spec section 2: a contact can belong to multiple organizations over time.';
