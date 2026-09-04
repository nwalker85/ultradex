-- 0005_interactions.sql
-- Spec section 7 "Communications and calendar".

-- ---------------------------------------------------------------------------
-- interaction_threads
-- ---------------------------------------------------------------------------
CREATE TABLE interaction_threads (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        uuid NOT NULL REFERENCES workspaces (id),
    channel             text NOT NULL,
    subject_commitment  text NULL,
    redacted_subject    text NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT interaction_threads_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE interaction_threads IS
    'Spec section 7: a communications thread grouping related interactions.';

CREATE TRIGGER trg_interaction_threads_updated_at
    BEFORE UPDATE ON interaction_threads
    FOR EACH ROW EXECUTE FUNCTION ccc_set_updated_at();

-- ---------------------------------------------------------------------------
-- interactions
-- ---------------------------------------------------------------------------
CREATE TABLE interactions (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id         uuid NOT NULL REFERENCES workspaces (id),
    thread_id            uuid NULL,
    interaction_type     text NOT NULL,
    direction            text NULL,
    subject_commitment   text NULL,
    redacted_subject     text NULL,
    redacted_summary     text NULL,
    content_ref          text NULL,
    content_commitment   text NULL,
    occurred_at          timestamptz NOT NULL,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT interactions_thread_fk
        FOREIGN KEY (workspace_id, thread_id)
        REFERENCES interaction_threads (workspace_id, id),
    CONSTRAINT interactions_type_chk
        CHECK (interaction_type IN ('email', 'linkedin_message', 'meeting', 'call', 'note')),
    CONSTRAINT interactions_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE interactions IS
    'Spec section 7: a communications/meeting record retaining provenance without importing raw content.';

CREATE TRIGGER trg_interactions_updated_at
    BEFORE UPDATE ON interactions
    FOR EACH ROW EXECUTE FUNCTION ccc_set_updated_at();

-- ---------------------------------------------------------------------------
-- interaction_contacts
-- ---------------------------------------------------------------------------
CREATE TABLE interaction_contacts (
    workspace_id       uuid NOT NULL REFERENCES workspaces (id),
    interaction_id     uuid NOT NULL,
    contact_id         uuid NOT NULL,
    participant_role   text NOT NULL,

    PRIMARY KEY (interaction_id, contact_id, participant_role),
    CONSTRAINT interaction_contacts_interaction_fk
        FOREIGN KEY (workspace_id, interaction_id)
        REFERENCES interactions (workspace_id, id),
    CONSTRAINT interaction_contacts_contact_fk
        FOREIGN KEY (workspace_id, contact_id)
        REFERENCES contacts (workspace_id, id)
);

COMMENT ON TABLE interaction_contacts IS
    'Spec section 7: an interaction can link to multiple contacts.';

-- ---------------------------------------------------------------------------
-- interaction_opportunities
-- ---------------------------------------------------------------------------
CREATE TABLE interaction_opportunities (
    workspace_id      uuid NOT NULL REFERENCES workspaces (id),
    interaction_id    uuid NOT NULL,
    opportunity_id    uuid NOT NULL,

    PRIMARY KEY (interaction_id, opportunity_id),
    CONSTRAINT interaction_opportunities_interaction_fk
        FOREIGN KEY (workspace_id, interaction_id)
        REFERENCES interactions (workspace_id, id),
    CONSTRAINT interaction_opportunities_opp_fk
        FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES opportunities (workspace_id, id)
);

COMMENT ON TABLE interaction_opportunities IS
    'Spec section 7: an interaction rolls up to an opportunity.';

-- ---------------------------------------------------------------------------
-- interaction_organizations
-- ---------------------------------------------------------------------------
CREATE TABLE interaction_organizations (
    workspace_id       uuid NOT NULL REFERENCES workspaces (id),
    interaction_id     uuid NOT NULL,
    organization_id    uuid NOT NULL,

    PRIMARY KEY (interaction_id, organization_id),
    CONSTRAINT interaction_organizations_interaction_fk
        FOREIGN KEY (workspace_id, interaction_id)
        REFERENCES interactions (workspace_id, id),
    CONSTRAINT interaction_organizations_org_fk
        FOREIGN KEY (workspace_id, organization_id)
        REFERENCES organizations (workspace_id, id)
);

COMMENT ON TABLE interaction_organizations IS
    'Spec section 7: an interaction rolls up to one or more organizations.';

-- ---------------------------------------------------------------------------
-- calendar_events
-- ---------------------------------------------------------------------------
CREATE TABLE calendar_events (
    interaction_id    uuid PRIMARY KEY,
    workspace_id      uuid NOT NULL REFERENCES workspaces (id),
    starts_at         timestamptz NOT NULL,
    ends_at           timestamptz NOT NULL,
    location_ref      text NULL,
    meeting_ref       text NULL,

    CONSTRAINT calendar_events_interaction_fk
        FOREIGN KEY (workspace_id, interaction_id)
        REFERENCES interactions (workspace_id, id)
);

COMMENT ON TABLE calendar_events IS
    'Spec section 7: scheduling facts for a meeting interaction; provider payloads stay in source custody.';
