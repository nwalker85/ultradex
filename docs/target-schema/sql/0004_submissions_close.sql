-- 0004_submissions_close.sql
-- Spec section 6 "Submissions and close evidence".

-- ---------------------------------------------------------------------------
-- submissions
-- ---------------------------------------------------------------------------
CREATE TABLE submissions (
    id                                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id                      uuid NOT NULL REFERENCES workspaces (id),
    opportunity_id                    uuid NOT NULL,
    submission_type                   text NOT NULL,
    channel                           text NULL,
    submitted_at                      timestamptz NULL,
    status                            text NOT NULL,
    external_reference_ref            text NULL,
    external_reference_commitment     text NULL,
    redacted_summary                  text NULL,
    created_at                        timestamptz NOT NULL DEFAULT now(),
    updated_at                        timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT submissions_opp_fk
        FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES opportunities (workspace_id, id),
    CONSTRAINT submissions_type_chk
        CHECK (submission_type IN ('application', 'proposal', 'rfp_response')),
    CONSTRAINT submissions_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE submissions IS
    'Spec section 6 + constraint 6: an application/proposal/RFP response child milestone under an opportunity.';

CREATE TRIGGER trg_submissions_updated_at
    BEFORE UPDATE ON submissions
    FOR EACH ROW EXECUTE FUNCTION ccc_set_updated_at();

-- ---------------------------------------------------------------------------
-- employment_offers
-- ---------------------------------------------------------------------------
CREATE TABLE employment_offers (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      uuid NOT NULL REFERENCES workspaces (id),
    opportunity_id    uuid NOT NULL,
    offered_at        timestamptz NOT NULL,
    compensation      numeric NULL,
    currency          char(3) NULL,
    start_date        date NULL,
    status            text NOT NULL,
    accepted_at       timestamptz NULL,

    CONSTRAINT employment_offers_opp_fk
        FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES opportunities (workspace_id, id),
    CONSTRAINT employment_offers_status_chk
        CHECK (status IN ('received', 'negotiating', 'accepted', 'declined'))
);

COMMENT ON TABLE employment_offers IS
    'Spec section 6 + constraint 7: employment close evidence; Closed Won employment requires an accepted row.';

-- ---------------------------------------------------------------------------
-- contract_agreements
-- ---------------------------------------------------------------------------
CREATE TABLE contract_agreements (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      uuid NOT NULL REFERENCES workspaces (id),
    opportunity_id    uuid NOT NULL,
    agreement_type    text NOT NULL,
    value             numeric NULL,
    currency          char(3) NULL,
    status            text NOT NULL,
    executed_at       timestamptz NULL,

    CONSTRAINT contract_agreements_opp_fk
        FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES opportunities (workspace_id, id),
    CONSTRAINT contract_agreements_type_chk
        CHECK (agreement_type IN ('contract', 'sow', 'subcontract')),
    CONSTRAINT contract_agreements_status_chk
        CHECK (status IN ('draft', 'sent', 'executed', 'rejected'))
);

COMMENT ON TABLE contract_agreements IS
    'Spec section 6 + constraint 8: contract close evidence; Closed Won contract requires an executed row.';
