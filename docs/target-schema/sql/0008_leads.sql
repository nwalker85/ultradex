-- 0008_leads.sql
-- Spec section 3 "Leads and conversion".
-- Ambiguity resolved: the spec never enumerates leads.motion, but its own
-- prose repeatedly names lead types as "W-2 Lead" and "contract Lead" (see
-- lead_qualification_snapshots discussion). motion is therefore closed to
-- 'w2' and 'contract' rather than mirroring opportunities.opportunity_type's
-- 'employment'/'contract' vocabulary.

-- ---------------------------------------------------------------------------
-- leads
-- ---------------------------------------------------------------------------
CREATE TABLE leads (
    id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id                uuid NOT NULL REFERENCES workspaces (id),
    status                      text NOT NULL,
    motion                      text NOT NULL,
    person_candidate_ref        text NULL,
    organization_candidate_ref  text NULL,
    title                       text NULL,
    source_type                 text NOT NULL,
    public_source_url           text NULL,
    redacted_summary            text NULL,
    source_commitment           text NOT NULL,
    discovered_at               timestamptz NOT NULL,
    qualified_at                timestamptz NULL,
    disqualified_reason         text NULL,
    created_at                  timestamptz NOT NULL DEFAULT now(),
    updated_at                  timestamptz NOT NULL DEFAULT now(),
    deleted_at                  timestamptz NULL,

    CONSTRAINT leads_status_chk
        CHECK (status IN ('new', 'nurturing', 'qualified', 'disqualified', 'converted')),
    CONSTRAINT leads_motion_chk
        CHECK (motion IN ('w2', 'contract')),
    CONSTRAINT leads_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE leads IS
    'Spec section 3: an unqualified signal preserved before Mimir/CCC resolution.';

CREATE TRIGGER trg_leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION ccc_set_updated_at();

-- Now that leads exists, complete the provenance link FK deferred from 0006.
ALTER TABLE lead_source_records
    ADD CONSTRAINT lead_source_records_lead_fk
    FOREIGN KEY (lead_id) REFERENCES leads (id);

-- ---------------------------------------------------------------------------
-- lead_compensation_overrides (immutable / append-only; trigger in 0011)
-- ---------------------------------------------------------------------------
CREATE TABLE lead_compensation_overrides (
    id                             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id                   uuid NOT NULL REFERENCES workspaces (id),
    lead_id                        uuid NOT NULL,
    policy_version                 text NOT NULL,
    annual_cash_floor              numeric NOT NULL,
    candidate_annual_cash          numeric NOT NULL,
    currency                       char(3) NOT NULL,
    redacted_reason                text NOT NULL,
    operator_principal_ref         text NOT NULL,
    operator_confirmation_ref      text NOT NULL,
    forseti_decision_ref           text NOT NULL,
    override_digest                text NOT NULL,
    approved_at                    timestamptz NOT NULL,
    expires_at                     timestamptz NOT NULL,
    supersedes_override_id         uuid NULL,
    created_at                     timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT lead_compensation_overrides_lead_fk
        FOREIGN KEY (workspace_id, lead_id)
        REFERENCES leads (workspace_id, id),
    CONSTRAINT lead_compensation_overrides_supersedes_fk
        FOREIGN KEY (workspace_id, supersedes_override_id)
        REFERENCES lead_compensation_overrides (workspace_id, id),
    -- "below floor" self-row sanity: an override only makes sense below the floor.
    CONSTRAINT lead_compensation_overrides_below_floor_chk
        CHECK (candidate_annual_cash < annual_cash_floor),
    CONSTRAINT lead_compensation_overrides_digest_uq UNIQUE (workspace_id, override_digest),
    CONSTRAINT lead_compensation_overrides_supersedes_uq UNIQUE (supersedes_override_id),
    CONSTRAINT lead_compensation_overrides_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE lead_compensation_overrides IS
    'Spec section 3: immutable, expiring, one-linear-history-per-policy operator override for a below-floor W-2 lead.';

-- Spec section 3: "Every successor must ... name the current immediately
-- prior override, producing one linear history per policy" -> at most one
-- open (non-superseded) override per workspace/lead/policy_version.
CREATE UNIQUE INDEX lead_compensation_overrides_open_uidx
    ON lead_compensation_overrides (workspace_id, lead_id, policy_version)
    WHERE supersedes_override_id IS NULL;

-- ---------------------------------------------------------------------------
-- lead_compensation_override_evidence (append-only)
-- ---------------------------------------------------------------------------
CREATE TABLE lead_compensation_override_evidence (
    workspace_id         uuid NOT NULL REFERENCES workspaces (id),
    override_id          uuid NOT NULL,
    ordinal              integer NOT NULL,
    evidence_ref         text NOT NULL,
    evidence_commitment  text NOT NULL,
    observed_at          timestamptz NOT NULL,

    PRIMARY KEY (override_id, ordinal),
    CONSTRAINT lead_compensation_override_evidence_override_fk
        FOREIGN KEY (workspace_id, override_id)
        REFERENCES lead_compensation_overrides (workspace_id, id),
    CONSTRAINT lead_compensation_override_evidence_uq UNIQUE (override_id, evidence_commitment)
);

COMMENT ON TABLE lead_compensation_override_evidence IS
    'Spec section 3: immutable evidence backing a compensation override.';

-- ---------------------------------------------------------------------------
-- lead_qualification_assessments (append-only; trigger in 0011)
-- ---------------------------------------------------------------------------
CREATE TABLE lead_qualification_assessments (
    id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id                uuid NOT NULL REFERENCES workspaces (id),
    lead_id                     uuid NOT NULL,
    dimension                   text NOT NULL,
    assessment                  text NOT NULL,
    policy_version               text NOT NULL,
    redacted_summary             text NULL,
    assessed_at                  timestamptz NOT NULL,
    assessor_type                text NOT NULL,
    supersedes_assessment_id     uuid NULL,
    created_at                   timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT lead_qualification_assessments_lead_fk
        FOREIGN KEY (workspace_id, lead_id)
        REFERENCES leads (workspace_id, id),
    CONSTRAINT lead_qualification_assessments_supersedes_fk
        FOREIGN KEY (workspace_id, supersedes_assessment_id)
        REFERENCES lead_qualification_assessments (workspace_id, id),
    CONSTRAINT lead_qualification_assessments_dimension_chk
        CHECK (dimension IN ('budget', 'authority', 'need', 'timeline')),
    CONSTRAINT lead_qualification_assessments_assessment_chk
        CHECK (assessment IN ('unknown', 'inferred', 'validated', 'contradicted')),
    CONSTRAINT lead_qualification_assessments_assessor_type_chk
        CHECK (assessor_type IN ('operator', 'deterministic_rule', 'agent_recommendation')),
    CONSTRAINT lead_qualification_assessments_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE lead_qualification_assessments IS
    'Spec section 3: append-only BANT dimension assessment for a lead.';

-- ---------------------------------------------------------------------------
-- lead_qualification_evidence (append-only; trigger in 0011)
-- ---------------------------------------------------------------------------
CREATE TABLE lead_qualification_evidence (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id           uuid NOT NULL REFERENCES workspaces (id),
    assessment_id          uuid NOT NULL,
    evidence_type          text NOT NULL,
    source_record_id       uuid NULL,
    interaction_id         uuid NULL,
    document_version_id    uuid NULL,
    public_source_url      text NULL,
    content_ref            text NULL,
    content_commitment     text NOT NULL,
    redacted_summary       text NULL,
    observed_at            timestamptz NOT NULL,
    created_at              timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT lead_qualification_evidence_assessment_fk
        FOREIGN KEY (workspace_id, assessment_id)
        REFERENCES lead_qualification_assessments (workspace_id, id),
    CONSTRAINT lead_qualification_evidence_source_record_fk
        FOREIGN KEY (workspace_id, source_record_id)
        REFERENCES source_records (workspace_id, id),
    CONSTRAINT lead_qualification_evidence_interaction_fk
        FOREIGN KEY (workspace_id, interaction_id)
        REFERENCES interactions (workspace_id, id),
    CONSTRAINT lead_qualification_evidence_document_version_fk
        FOREIGN KEY (workspace_id, document_version_id)
        REFERENCES document_versions (workspace_id, id),
    CONSTRAINT lead_qualification_evidence_type_chk
        CHECK (evidence_type IN ('source_record', 'interaction', 'document', 'public_url', 'content_ref')),
    -- Constraint 18 (lead-specific half): exactly one typed evidence target.
    CONSTRAINT lead_qualification_evidence_exactly_one_target_chk
        CHECK (
            (evidence_type = 'source_record'
                AND source_record_id IS NOT NULL AND interaction_id IS NULL
                AND document_version_id IS NULL AND public_source_url IS NULL AND content_ref IS NULL)
            OR (evidence_type = 'interaction'
                AND interaction_id IS NOT NULL AND source_record_id IS NULL
                AND document_version_id IS NULL AND public_source_url IS NULL AND content_ref IS NULL)
            OR (evidence_type = 'document'
                AND document_version_id IS NOT NULL AND source_record_id IS NULL
                AND interaction_id IS NULL AND public_source_url IS NULL AND content_ref IS NULL)
            OR (evidence_type = 'public_url'
                AND public_source_url IS NOT NULL AND source_record_id IS NULL
                AND interaction_id IS NULL AND document_version_id IS NULL AND content_ref IS NULL)
            OR (evidence_type = 'content_ref'
                AND content_ref IS NOT NULL AND source_record_id IS NULL
                AND interaction_id IS NULL AND document_version_id IS NULL AND public_source_url IS NULL)
        )
);

COMMENT ON TABLE lead_qualification_evidence IS
    'Spec section 3 + constraint 18: append-only, exactly-one-typed-target evidence for a BANT assessment.';

-- ---------------------------------------------------------------------------
-- lead_qualification_snapshots (append-only; trigger in 0011)
-- ---------------------------------------------------------------------------
CREATE TABLE lead_qualification_snapshots (
    id                              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id                    uuid NOT NULL REFERENCES workspaces (id),
    lead_id                         uuid NOT NULL,
    policy_version                  text NOT NULL,
    qualification_state             text NOT NULL,
    w2_annual_cash_amount           numeric NULL,
    w2_annual_cash_currency         char(3) NULL,
    w2_annual_cash_evidence_digest  text NULL,
    compensation_override_id        uuid NULL,
    snapshot_digest                 text NOT NULL,
    created_at                      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT lead_qualification_snapshots_lead_fk
        FOREIGN KEY (workspace_id, lead_id)
        REFERENCES leads (workspace_id, id),
    CONSTRAINT lead_qualification_snapshots_override_fk
        FOREIGN KEY (workspace_id, compensation_override_id)
        REFERENCES lead_compensation_overrides (workspace_id, id),
    CONSTRAINT lead_qualification_snapshots_state_chk
        CHECK (qualification_state IN ('nurturing', 'qualified')),
    -- Field-presence half of constraint 23: the three W-2 fields travel together.
    CONSTRAINT lead_qualification_snapshots_w2_fields_together_chk
        CHECK (
            (w2_annual_cash_amount IS NULL AND w2_annual_cash_currency IS NULL AND w2_annual_cash_evidence_digest IS NULL)
            OR (w2_annual_cash_amount IS NOT NULL AND w2_annual_cash_currency IS NOT NULL AND w2_annual_cash_evidence_digest IS NOT NULL)
        ),
    -- Field-presence half of constraint 22: an override only ever attaches to
    -- a snapshot that carries W-2 fields (cross-row "was it actually below
    -- floor / same Lead / current" checks are the deferred trigger in 0011).
    CONSTRAINT lead_qualification_snapshots_override_implies_w2_chk
        CHECK (compensation_override_id IS NULL OR w2_annual_cash_amount IS NOT NULL),
    CONSTRAINT lead_qualification_snapshots_digest_uq UNIQUE (workspace_id, snapshot_digest),
    CONSTRAINT lead_qualification_snapshots_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE lead_qualification_snapshots IS
    'Spec section 3 + constraints 17/22/23: immutable, digest-committed BANT+compensation snapshot for a lead.';

-- ---------------------------------------------------------------------------
-- lead_qualification_snapshot_assessments (append-only; trigger in 0011)
-- ---------------------------------------------------------------------------
CREATE TABLE lead_qualification_snapshot_assessments (
    workspace_id     uuid NOT NULL REFERENCES workspaces (id),
    snapshot_id      uuid NOT NULL,
    dimension        text NOT NULL,
    assessment_id    uuid NOT NULL,

    PRIMARY KEY (snapshot_id, dimension),
    CONSTRAINT lead_qual_snapshot_assessments_snapshot_fk
        FOREIGN KEY (workspace_id, snapshot_id)
        REFERENCES lead_qualification_snapshots (workspace_id, id),
    CONSTRAINT lead_qual_snapshot_assessments_assessment_fk
        FOREIGN KEY (workspace_id, assessment_id)
        REFERENCES lead_qualification_assessments (workspace_id, id),
    CONSTRAINT lead_qual_snapshot_assessments_dimension_chk
        CHECK (dimension IN ('budget', 'authority', 'need', 'timeline')),
    CONSTRAINT lead_qual_snapshot_assessments_uq UNIQUE (snapshot_id, assessment_id)
);

COMMENT ON TABLE lead_qualification_snapshot_assessments IS
    'Spec section 3 + constraint 17: the exactly-four (one per BANT dimension) child rows of a snapshot.';

-- ---------------------------------------------------------------------------
-- lead_booking_proofs (append-only; triggers in 0011)
-- ---------------------------------------------------------------------------
CREATE TABLE lead_booking_proofs (
    id                            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id                  uuid NOT NULL REFERENCES workspaces (id),
    lead_id                       uuid NOT NULL,
    interaction_id                uuid NOT NULL,
    scheduling_provider           text NOT NULL,
    provider_event_ref            text NOT NULL,
    provider_event_commitment     text NOT NULL,
    booking_identity_digest       text NOT NULL,
    observation_fingerprint       text NOT NULL,
    observation_version           integer NOT NULL,
    event_status                  text NOT NULL,
    starts_at                     timestamptz NOT NULL,
    ends_at                       timestamptz NOT NULL,
    observed_at                   timestamptz NOT NULL,
    proof_digest                  text NOT NULL,
    supersedes_booking_proof_id   uuid NULL,
    created_at                    timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT lead_booking_proofs_lead_fk
        FOREIGN KEY (workspace_id, lead_id)
        REFERENCES leads (workspace_id, id),
    CONSTRAINT lead_booking_proofs_interaction_fk
        FOREIGN KEY (workspace_id, interaction_id)
        REFERENCES interactions (workspace_id, id),
    CONSTRAINT lead_booking_proofs_supersedes_fk
        FOREIGN KEY (workspace_id, supersedes_booking_proof_id)
        REFERENCES lead_booking_proofs (workspace_id, id),
    CONSTRAINT lead_booking_proofs_event_status_chk
        CHECK (event_status IN ('confirmed', 'cancelled')),
    -- Spec section 3: "has ends_at > starts_at".
    CONSTRAINT lead_booking_proofs_time_order_chk
        CHECK (ends_at > starts_at),
    CONSTRAINT lead_booking_proofs_version_positive_chk
        CHECK (observation_version >= 1),

    CONSTRAINT lead_booking_proofs_identity_version_uq
        UNIQUE (workspace_id, booking_identity_digest, observation_version),
    CONSTRAINT lead_booking_proofs_identity_fingerprint_uq
        UNIQUE (workspace_id, booking_identity_digest, observation_fingerprint),
    CONSTRAINT lead_booking_proofs_supersedes_uq
        UNIQUE (supersedes_booking_proof_id),
    CONSTRAINT lead_booking_proofs_proof_digest_uq
        UNIQUE (workspace_id, proof_digest),
    CONSTRAINT lead_booking_proofs_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE lead_booking_proofs IS
    'Spec section 3 + constraint 19: immutable, append-only linear chain of scheduling observations for a lead.';

-- Spec section 3: "Unique predecessor and identity/version constraints make
-- one linear append-only chain" -> at most one open (non-superseded) proof
-- per workspace/booking identity.
CREATE UNIQUE INDEX lead_booking_proofs_open_uidx
    ON lead_booking_proofs (workspace_id, booking_identity_digest)
    WHERE supersedes_booking_proof_id IS NULL;

-- ---------------------------------------------------------------------------
-- lead_booking_participants (append-only; trigger in 0011)
-- ---------------------------------------------------------------------------
CREATE TABLE lead_booking_participants (
    workspace_id             uuid NOT NULL REFERENCES workspaces (id),
    booking_proof_id         uuid NOT NULL,
    participant_ref          text NOT NULL,
    participant_commitment   text NOT NULL,
    is_external              boolean NOT NULL,

    PRIMARY KEY (booking_proof_id, participant_commitment),
    CONSTRAINT lead_booking_participants_proof_fk
        FOREIGN KEY (workspace_id, booking_proof_id)
        REFERENCES lead_booking_proofs (workspace_id, id)
);

COMMENT ON TABLE lead_booking_participants IS
    'Spec section 3 + constraint 19: participants of a booking proof; at least one must be external.';

-- ---------------------------------------------------------------------------
-- lead_conversions (append-only; trigger in 0011)
-- ---------------------------------------------------------------------------
CREATE TABLE lead_conversions (
    id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id                uuid NOT NULL REFERENCES workspaces (id),
    lead_id                     uuid NOT NULL,
    qualification_snapshot_id   uuid NOT NULL,
    booking_proof_id            uuid NOT NULL,
    organization_id             uuid NOT NULL,
    contact_id                  uuid NOT NULL,
    opportunity_id              uuid NOT NULL,
    converted_at                timestamptz NOT NULL,

    CONSTRAINT lead_conversions_lead_fk
        FOREIGN KEY (workspace_id, lead_id)
        REFERENCES leads (workspace_id, id),
    CONSTRAINT lead_conversions_snapshot_fk
        FOREIGN KEY (workspace_id, qualification_snapshot_id)
        REFERENCES lead_qualification_snapshots (workspace_id, id),
    CONSTRAINT lead_conversions_booking_proof_fk
        FOREIGN KEY (workspace_id, booking_proof_id)
        REFERENCES lead_booking_proofs (workspace_id, id),
    CONSTRAINT lead_conversions_org_fk
        FOREIGN KEY (workspace_id, organization_id)
        REFERENCES organizations (workspace_id, id),
    CONSTRAINT lead_conversions_contact_fk
        FOREIGN KEY (workspace_id, contact_id)
        REFERENCES contacts (workspace_id, id),
    CONSTRAINT lead_conversions_opportunity_fk
        FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES opportunities (workspace_id, id),

    CONSTRAINT lead_conversions_lead_uq UNIQUE (lead_id),
    CONSTRAINT lead_conversions_snapshot_uq UNIQUE (qualification_snapshot_id),
    CONSTRAINT lead_conversions_booking_proof_uq UNIQUE (booking_proof_id)
);

COMMENT ON TABLE lead_conversions IS
    'Spec section 3 + constraint 2/20: the single, immutable, atomic conversion record for a lead.';
