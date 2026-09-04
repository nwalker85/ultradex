-- 0003_funnel.sql
-- Spec section 4 "Shared opportunity funnel" and section 5 "Type-specific
-- opportunity details".

-- ---------------------------------------------------------------------------
-- pipelines
-- ---------------------------------------------------------------------------
CREATE TABLE pipelines (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id   uuid NOT NULL REFERENCES workspaces (id),
    code           text NOT NULL,
    name           text NOT NULL,

    CONSTRAINT pipelines_workspace_code_uq UNIQUE (workspace_id, code),
    CONSTRAINT pipelines_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE pipelines IS
    'Spec section 4: CCC seeds one shared career-opportunity pipeline per workspace.';

-- ---------------------------------------------------------------------------
-- pipeline_stages
-- The spec does not carry workspace_id on this table; workspace scope is
-- transitive through pipeline_id -> pipelines.workspace_id.
-- ---------------------------------------------------------------------------
CREATE TABLE pipeline_stages (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id   uuid NOT NULL REFERENCES pipelines (id),
    code          text NOT NULL,
    name          text NOT NULL,
    ordinal       integer NOT NULL,
    outcome       text NULL,

    CONSTRAINT pipeline_stages_pipeline_code_uq UNIQUE (pipeline_id, code),
    CONSTRAINT pipeline_stages_pipeline_ordinal_uq UNIQUE (pipeline_id, ordinal),
    -- Needed so opportunities can composite-FK (stage_id, pipeline_id) and the
    -- database itself proves an opportunity's stage belongs to its pipeline
    -- (spec section 4 + constraint 3).
    CONSTRAINT pipeline_stages_id_pipeline_uq UNIQUE (id, pipeline_id),
    CONSTRAINT pipeline_stages_outcome_chk
        CHECK (outcome IS NULL OR outcome IN ('won', 'lost'))
);

COMMENT ON TABLE pipeline_stages IS
    'Spec section 4: ordered stages of a pipeline; outcome is set only on terminal (Closed Won/Lost) stages.';

-- ---------------------------------------------------------------------------
-- opportunities
-- ---------------------------------------------------------------------------
CREATE TABLE opportunities (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id          uuid NOT NULL REFERENCES workspaces (id),
    pipeline_id           uuid NOT NULL,
    stage_id              uuid NOT NULL,
    opportunity_type      text NOT NULL,
    name                  text NOT NULL,
    role_title            text NULL,
    description           text NULL,
    opened_at             timestamptz NOT NULL,
    expected_close_date   date NULL,
    probability           numeric(5, 2) NULL,
    closed_at             timestamptz NULL,
    lost_reason           text NULL,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    deleted_at            timestamptz NULL,

    CONSTRAINT opportunities_pipeline_fk
        FOREIGN KEY (workspace_id, pipeline_id)
        REFERENCES pipelines (workspace_id, id),
    -- Constraint 3 / spec section 4: an opportunity's stage belongs to its pipeline.
    CONSTRAINT opportunities_stage_in_pipeline_fk
        FOREIGN KEY (stage_id, pipeline_id)
        REFERENCES pipeline_stages (id, pipeline_id),
    CONSTRAINT opportunities_type_chk
        CHECK (opportunity_type IN ('employment', 'contract')),

    CONSTRAINT opportunities_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE opportunities IS
    'Spec section 4: one specific pursuit at one or more related organizations; shared employment/contract funnel.';

CREATE TRIGGER trg_opportunities_updated_at
    BEFORE UPDATE ON opportunities
    FOR EACH ROW EXECUTE FUNCTION ccc_set_updated_at();

-- ---------------------------------------------------------------------------
-- opportunity_organizations
-- ---------------------------------------------------------------------------
CREATE TABLE opportunity_organizations (
    workspace_id      uuid NOT NULL REFERENCES workspaces (id),
    opportunity_id    uuid NOT NULL,
    organization_id   uuid NOT NULL,
    role              text NOT NULL,
    is_primary        boolean NOT NULL DEFAULT false,

    PRIMARY KEY (opportunity_id, organization_id, role),
    CONSTRAINT opportunity_organizations_opp_fk
        FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES opportunities (workspace_id, id),
    CONSTRAINT opportunity_organizations_org_fk
        FOREIGN KEY (workspace_id, organization_id)
        REFERENCES organizations (workspace_id, id),
    CONSTRAINT opportunity_organizations_role_chk
        CHECK (role IN ('employer', 'client', 'agency', 'consultancy', 'partner', 'other'))
);

COMMENT ON TABLE opportunity_organizations IS
    'Spec section 4: organizations play contextual roles on an opportunity.';

-- Spec section 4: "A partial unique index permits at most one primary
-- organization per opportunity and role."
CREATE UNIQUE INDEX opportunity_organizations_primary_uidx
    ON opportunity_organizations (opportunity_id, role)
    WHERE is_primary;

-- ---------------------------------------------------------------------------
-- opportunity_contacts
-- ---------------------------------------------------------------------------
CREATE TABLE opportunity_contacts (
    workspace_id             uuid NOT NULL REFERENCES workspaces (id),
    opportunity_id           uuid NOT NULL,
    contact_id               uuid NOT NULL,
    role                     text NOT NULL,
    influence_level          text NULL,
    relationship_strength    integer NULL,
    is_primary               boolean NOT NULL DEFAULT false,

    PRIMARY KEY (opportunity_id, contact_id, role),
    CONSTRAINT opportunity_contacts_opp_fk
        FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES opportunities (workspace_id, id),
    CONSTRAINT opportunity_contacts_contact_fk
        FOREIGN KEY (workspace_id, contact_id)
        REFERENCES contacts (workspace_id, id),
    CONSTRAINT opportunity_contacts_role_chk
        CHECK (role IN ('recruiter', 'hiring_manager', 'champion', 'decision_maker', 'economic_buyer', 'other'))
);

COMMENT ON TABLE opportunity_contacts IS
    'Spec section 4: contacts play contextual roles on an opportunity.';

-- ---------------------------------------------------------------------------
-- opportunity_stage_history (append-only; trigger added in 0011)
-- ---------------------------------------------------------------------------
CREATE TABLE opportunity_stage_history (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      uuid NOT NULL REFERENCES workspaces (id),
    opportunity_id    uuid NOT NULL,
    from_stage_id     uuid NULL REFERENCES pipeline_stages (id),
    to_stage_id       uuid NOT NULL REFERENCES pipeline_stages (id),
    changed_at        timestamptz NOT NULL,
    reason            text NULL,

    CONSTRAINT opportunity_stage_history_opp_fk
        FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES opportunities (workspace_id, id)
);

COMMENT ON TABLE opportunity_stage_history IS
    'Spec section 4 + constraint 9: append-only audit trail of stage transitions.';

-- ---------------------------------------------------------------------------
-- employment_opportunity_details
-- ---------------------------------------------------------------------------
CREATE TABLE employment_opportunity_details (
    opportunity_id     uuid PRIMARY KEY,
    workspace_id       uuid NOT NULL REFERENCES workspaces (id),
    employment_type    text NULL,
    location           text NULL,
    remote_policy      text NULL,
    requisition_id     text NULL,
    job_posting_url    text NULL,
    compensation_min   numeric NULL,
    compensation_max   numeric NULL,
    currency           char(3) NULL,

    CONSTRAINT employment_opportunity_details_opp_fk
        FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES opportunities (workspace_id, id)
);

COMMENT ON TABLE employment_opportunity_details IS
    'Spec section 5: type-specific detail for opportunity_type = employment.';

-- ---------------------------------------------------------------------------
-- contract_opportunity_details
-- ---------------------------------------------------------------------------
CREATE TABLE contract_opportunity_details (
    opportunity_id        uuid PRIMARY KEY,
    workspace_id          uuid NOT NULL REFERENCES workspaces (id),
    engagement_model      text NULL,
    rate                  numeric NULL,
    rate_unit             text NULL,
    estimated_value       numeric NULL,
    currency              char(3) NULL,
    expected_start_date   date NULL,
    expected_end_date     date NULL,

    CONSTRAINT contract_opportunity_details_opp_fk
        FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES opportunities (workspace_id, id),
    CONSTRAINT contract_opportunity_details_engagement_chk
        CHECK (engagement_model IS NULL OR engagement_model IN ('direct', 'corp_to_corp', 'subcontract')),
    CONSTRAINT contract_opportunity_details_rate_unit_chk
        CHECK (rate_unit IS NULL OR rate_unit IN ('hour', 'day', 'month', 'fixed'))
);

COMMENT ON TABLE contract_opportunity_details IS
    'Spec section 5: type-specific detail for opportunity_type = contract.';
