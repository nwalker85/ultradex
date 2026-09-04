-- 0010_actions_nba.sql
-- Spec section 11 "Actions, rankings, and next best action".

-- ---------------------------------------------------------------------------
-- actions
-- ---------------------------------------------------------------------------
CREATE TABLE actions (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id   uuid NOT NULL REFERENCES workspaces (id),
    action_type    text NOT NULL,
    status         text NOT NULL,
    title          text NOT NULL,
    rationale      text NULL,
    due_at         timestamptz NULL,
    completed_at   timestamptz NULL,
    expires_at     timestamptz NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT actions_status_chk
        CHECK (status IN ('proposed', 'ready', 'completed', 'dismissed', 'expired')),
    CONSTRAINT actions_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE actions IS
    'Spec section 11: a first-class, workspace-owned recommended or executed action.';

CREATE TRIGGER trg_actions_updated_at
    BEFORE UPDATE ON actions
    FOR EACH ROW EXECUTE FUNCTION ccc_set_updated_at();

-- ---------------------------------------------------------------------------
-- action_* link tables. The spec writes these WITHOUT workspace_id; a BEFORE
-- INSERT/UPDATE trigger (added in 0011) asserts both endpoints share a
-- workspace (constraint 13).
-- ---------------------------------------------------------------------------
CREATE TABLE action_opportunities (
    action_id         uuid NOT NULL REFERENCES actions (id),
    opportunity_id    uuid NOT NULL REFERENCES opportunities (id),

    PRIMARY KEY (action_id, opportunity_id)
);

COMMENT ON TABLE action_opportunities IS
    'Spec section 11: an action can target one or more opportunities.';

CREATE TABLE action_contacts (
    action_id     uuid NOT NULL REFERENCES actions (id),
    contact_id    uuid NOT NULL REFERENCES contacts (id),

    PRIMARY KEY (action_id, contact_id)
);

COMMENT ON TABLE action_contacts IS
    'Spec section 11: an action can target one or more contacts.';

CREATE TABLE action_organizations (
    action_id          uuid NOT NULL REFERENCES actions (id),
    organization_id    uuid NOT NULL REFERENCES organizations (id),

    PRIMARY KEY (action_id, organization_id)
);

COMMENT ON TABLE action_organizations IS
    'Spec section 11: an action can target one or more organizations.';

CREATE TABLE action_leads (
    action_id    uuid NOT NULL REFERENCES actions (id),
    lead_id      uuid NOT NULL REFERENCES leads (id),

    PRIMARY KEY (action_id, lead_id)
);

COMMENT ON TABLE action_leads IS
    'Spec section 11: an action can target one or more leads.';

-- ---------------------------------------------------------------------------
-- scoring_runs
-- ---------------------------------------------------------------------------
CREATE TABLE scoring_runs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces (id),
    model_name      text NOT NULL,
    model_version   text NOT NULL,
    started_at      timestamptz NOT NULL,
    completed_at    timestamptz NULL,

    CONSTRAINT scoring_runs_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE scoring_runs IS
    'Spec section 11: one execution of an action-ranking model.';

-- ---------------------------------------------------------------------------
-- action_scores
-- ---------------------------------------------------------------------------
CREATE TABLE action_scores (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        uuid NOT NULL REFERENCES workspaces (id),
    action_id           uuid NOT NULL,
    scoring_run_id      uuid NOT NULL,
    total_score         numeric NOT NULL,
    score_components    jsonb NOT NULL,
    scored_at           timestamptz NOT NULL,

    CONSTRAINT action_scores_action_fk
        FOREIGN KEY (workspace_id, action_id)
        REFERENCES actions (workspace_id, id),
    CONSTRAINT action_scores_scoring_run_fk
        FOREIGN KEY (workspace_id, scoring_run_id)
        REFERENCES scoring_runs (workspace_id, id)
);

COMMENT ON TABLE action_scores IS
    'Spec section 11: scoring provenance for a candidate action from a scoring run.';

-- ---------------------------------------------------------------------------
-- next_best_action
-- workspace_id as PRIMARY KEY structurally enforces constraint 12: a
-- workspace has at most one current next-best-action pointer.
-- ---------------------------------------------------------------------------
CREATE TABLE next_best_action (
    workspace_id      uuid PRIMARY KEY REFERENCES workspaces (id),
    action_id         uuid NOT NULL,
    selected_at       timestamptz NOT NULL,
    scoring_run_id    uuid NULL,

    CONSTRAINT next_best_action_action_fk
        FOREIGN KEY (workspace_id, action_id)
        REFERENCES actions (workspace_id, id),
    CONSTRAINT next_best_action_action_uq UNIQUE (action_id),
    CONSTRAINT next_best_action_scoring_run_fk
        FOREIGN KEY (workspace_id, scoring_run_id)
        REFERENCES scoring_runs (workspace_id, id)
);

COMMENT ON TABLE next_best_action IS
    'Spec section 11 + constraint 12: the single authoritative next-best-action pointer per workspace.';
