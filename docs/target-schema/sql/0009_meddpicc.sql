-- 0009_meddpicc.sql
-- Spec section 10 "MEDDPICC qualification and evidence".

-- ---------------------------------------------------------------------------
-- opportunity_qualification
-- ---------------------------------------------------------------------------
CREATE TABLE opportunity_qualification (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      uuid NOT NULL REFERENCES workspaces (id),
    opportunity_id    uuid NOT NULL,
    dimension         text NOT NULL,
    status            text NOT NULL,
    score             numeric NULL,
    redacted_summary  text NULL,
    validated_at      timestamptz NULL,
    updated_at        timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT opportunity_qualification_opp_fk
        FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES opportunities (workspace_id, id),
    CONSTRAINT opportunity_qualification_dimension_chk
        CHECK (dimension IN ('metrics', 'economic_buyer', 'decision_criteria', 'decision_process',
                              'paper_process', 'identify_pain', 'champion', 'competition')),
    CONSTRAINT opportunity_qualification_status_chk
        CHECK (status IN ('unknown', 'weak', 'developing', 'validated')),
    CONSTRAINT opportunity_qualification_opp_dimension_uq UNIQUE (opportunity_id, dimension),
    CONSTRAINT opportunity_qualification_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE opportunity_qualification IS
    'Spec section 10: MEDDPICC dimension status for an opportunity, distinct from the pre-conversion Lead BANT gate.';

CREATE TRIGGER trg_opportunity_qualification_updated_at
    BEFORE UPDATE ON opportunity_qualification
    FOR EACH ROW EXECUTE FUNCTION ccc_set_updated_at();

-- ---------------------------------------------------------------------------
-- qualification_evidence
-- ---------------------------------------------------------------------------
CREATE TABLE qualification_evidence (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id          uuid NOT NULL REFERENCES workspaces (id),
    qualification_id      uuid NOT NULL,
    interaction_id         uuid NULL,
    document_version_id    uuid NULL,
    contact_id              uuid NULL,
    redacted_summary        text NULL,
    created_at               timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT qualification_evidence_qualification_fk
        FOREIGN KEY (workspace_id, qualification_id)
        REFERENCES opportunity_qualification (workspace_id, id),
    CONSTRAINT qualification_evidence_interaction_fk
        FOREIGN KEY (workspace_id, interaction_id)
        REFERENCES interactions (workspace_id, id),
    CONSTRAINT qualification_evidence_document_version_fk
        FOREIGN KEY (workspace_id, document_version_id)
        REFERENCES document_versions (workspace_id, id),
    CONSTRAINT qualification_evidence_contact_fk
        FOREIGN KEY (workspace_id, contact_id)
        REFERENCES contacts (workspace_id, id),
    -- Constraint 18 (opportunity-qualification half): at least one target.
    CONSTRAINT qualification_evidence_at_least_one_target_chk
        CHECK (interaction_id IS NOT NULL OR document_version_id IS NOT NULL OR contact_id IS NOT NULL)
);

COMMENT ON TABLE qualification_evidence IS
    'Spec section 10 + constraint 18: at-least-one-typed-target evidence for a MEDDPICC dimension.';
