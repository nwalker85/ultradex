-- 0011_constraints.sql
-- Append-only triggers, workspace-match triggers for link tables without
-- workspace_id, and DEFERRABLE INITIALLY DEFERRED constraint triggers for
-- the cross-row invariants the CHECK constraints in earlier files cannot
-- express alone.

-- =============================================================================
-- Append-only enforcement (constraint 9 and the append-only tables named in
-- the brief: stage history, score snapshots (action_scores), source-record
-- versions, document versions, lead assessments/evidence/snapshots/overrides/
-- booking proofs, lead_compensation_override_evidence, snapshot_assessments,
-- booking participants, conversions).
-- =============================================================================

CREATE TRIGGER trg_append_only_opportunity_stage_history
    BEFORE UPDATE OR DELETE ON opportunity_stage_history
    FOR EACH ROW EXECUTE FUNCTION ccc_reject_mutation();

CREATE TRIGGER trg_append_only_action_scores
    BEFORE UPDATE OR DELETE ON action_scores
    FOR EACH ROW EXECUTE FUNCTION ccc_reject_mutation();

CREATE TRIGGER trg_append_only_source_record_versions
    BEFORE UPDATE OR DELETE ON source_record_versions
    FOR EACH ROW EXECUTE FUNCTION ccc_reject_mutation();

CREATE TRIGGER trg_append_only_document_versions
    BEFORE UPDATE OR DELETE ON document_versions
    FOR EACH ROW EXECUTE FUNCTION ccc_reject_mutation();

CREATE TRIGGER trg_append_only_lead_qualification_assessments
    BEFORE UPDATE OR DELETE ON lead_qualification_assessments
    FOR EACH ROW EXECUTE FUNCTION ccc_reject_mutation();

CREATE TRIGGER trg_append_only_lead_qualification_evidence
    BEFORE UPDATE OR DELETE ON lead_qualification_evidence
    FOR EACH ROW EXECUTE FUNCTION ccc_reject_mutation();

CREATE TRIGGER trg_append_only_lead_qualification_snapshots
    BEFORE UPDATE OR DELETE ON lead_qualification_snapshots
    FOR EACH ROW EXECUTE FUNCTION ccc_reject_mutation();

CREATE TRIGGER trg_append_only_lead_qualification_snapshot_assessments
    BEFORE UPDATE OR DELETE ON lead_qualification_snapshot_assessments
    FOR EACH ROW EXECUTE FUNCTION ccc_reject_mutation();

CREATE TRIGGER trg_append_only_lead_compensation_overrides
    BEFORE UPDATE OR DELETE ON lead_compensation_overrides
    FOR EACH ROW EXECUTE FUNCTION ccc_reject_mutation();

CREATE TRIGGER trg_append_only_lead_compensation_override_evidence
    BEFORE UPDATE OR DELETE ON lead_compensation_override_evidence
    FOR EACH ROW EXECUTE FUNCTION ccc_reject_mutation();

CREATE TRIGGER trg_append_only_lead_booking_proofs
    BEFORE UPDATE OR DELETE ON lead_booking_proofs
    FOR EACH ROW EXECUTE FUNCTION ccc_reject_mutation();

CREATE TRIGGER trg_append_only_lead_booking_participants
    BEFORE UPDATE OR DELETE ON lead_booking_participants
    FOR EACH ROW EXECUTE FUNCTION ccc_reject_mutation();

CREATE TRIGGER trg_append_only_lead_conversions
    BEFORE UPDATE OR DELETE ON lead_conversions
    FOR EACH ROW EXECUTE FUNCTION ccc_reject_mutation();

-- =============================================================================
-- Constraint 13 workspace-match triggers for link tables the spec writes
-- WITHOUT workspace_id.
-- =============================================================================

CREATE OR REPLACE FUNCTION ccc_ws_organization_source_records() RETURNS trigger AS $$
DECLARE ws_a uuid; ws_b uuid;
BEGIN
    SELECT workspace_id INTO ws_a FROM organizations WHERE id = NEW.organization_id;
    SELECT workspace_id INTO ws_b FROM source_records WHERE id = NEW.source_record_id;
    PERFORM ccc_assert_same_workspace(ws_a, ws_b, 'organization_source_records');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ws_organization_source_records
    BEFORE INSERT OR UPDATE ON organization_source_records
    FOR EACH ROW EXECUTE FUNCTION ccc_ws_organization_source_records();

CREATE OR REPLACE FUNCTION ccc_ws_contact_source_records() RETURNS trigger AS $$
DECLARE ws_a uuid; ws_b uuid;
BEGIN
    SELECT workspace_id INTO ws_a FROM contacts WHERE id = NEW.contact_id;
    SELECT workspace_id INTO ws_b FROM source_records WHERE id = NEW.source_record_id;
    PERFORM ccc_assert_same_workspace(ws_a, ws_b, 'contact_source_records');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ws_contact_source_records
    BEFORE INSERT OR UPDATE ON contact_source_records
    FOR EACH ROW EXECUTE FUNCTION ccc_ws_contact_source_records();

CREATE OR REPLACE FUNCTION ccc_ws_lead_source_records() RETURNS trigger AS $$
DECLARE ws_a uuid; ws_b uuid;
BEGIN
    SELECT workspace_id INTO ws_a FROM leads WHERE id = NEW.lead_id;
    SELECT workspace_id INTO ws_b FROM source_records WHERE id = NEW.source_record_id;
    PERFORM ccc_assert_same_workspace(ws_a, ws_b, 'lead_source_records');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ws_lead_source_records
    BEFORE INSERT OR UPDATE ON lead_source_records
    FOR EACH ROW EXECUTE FUNCTION ccc_ws_lead_source_records();

CREATE OR REPLACE FUNCTION ccc_ws_interaction_source_records() RETURNS trigger AS $$
DECLARE ws_a uuid; ws_b uuid;
BEGIN
    SELECT workspace_id INTO ws_a FROM interactions WHERE id = NEW.interaction_id;
    SELECT workspace_id INTO ws_b FROM source_records WHERE id = NEW.source_record_id;
    PERFORM ccc_assert_same_workspace(ws_a, ws_b, 'interaction_source_records');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ws_interaction_source_records
    BEFORE INSERT OR UPDATE ON interaction_source_records
    FOR EACH ROW EXECUTE FUNCTION ccc_ws_interaction_source_records();

CREATE OR REPLACE FUNCTION ccc_ws_opportunity_source_records() RETURNS trigger AS $$
DECLARE ws_a uuid; ws_b uuid;
BEGIN
    SELECT workspace_id INTO ws_a FROM opportunities WHERE id = NEW.opportunity_id;
    SELECT workspace_id INTO ws_b FROM source_records WHERE id = NEW.source_record_id;
    PERFORM ccc_assert_same_workspace(ws_a, ws_b, 'opportunity_source_records');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ws_opportunity_source_records
    BEFORE INSERT OR UPDATE ON opportunity_source_records
    FOR EACH ROW EXECUTE FUNCTION ccc_ws_opportunity_source_records();

CREATE OR REPLACE FUNCTION ccc_ws_action_opportunities() RETURNS trigger AS $$
DECLARE ws_a uuid; ws_b uuid;
BEGIN
    SELECT workspace_id INTO ws_a FROM actions WHERE id = NEW.action_id;
    SELECT workspace_id INTO ws_b FROM opportunities WHERE id = NEW.opportunity_id;
    PERFORM ccc_assert_same_workspace(ws_a, ws_b, 'action_opportunities');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ws_action_opportunities
    BEFORE INSERT OR UPDATE ON action_opportunities
    FOR EACH ROW EXECUTE FUNCTION ccc_ws_action_opportunities();

CREATE OR REPLACE FUNCTION ccc_ws_action_contacts() RETURNS trigger AS $$
DECLARE ws_a uuid; ws_b uuid;
BEGIN
    SELECT workspace_id INTO ws_a FROM actions WHERE id = NEW.action_id;
    SELECT workspace_id INTO ws_b FROM contacts WHERE id = NEW.contact_id;
    PERFORM ccc_assert_same_workspace(ws_a, ws_b, 'action_contacts');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ws_action_contacts
    BEFORE INSERT OR UPDATE ON action_contacts
    FOR EACH ROW EXECUTE FUNCTION ccc_ws_action_contacts();

CREATE OR REPLACE FUNCTION ccc_ws_action_organizations() RETURNS trigger AS $$
DECLARE ws_a uuid; ws_b uuid;
BEGIN
    SELECT workspace_id INTO ws_a FROM actions WHERE id = NEW.action_id;
    SELECT workspace_id INTO ws_b FROM organizations WHERE id = NEW.organization_id;
    PERFORM ccc_assert_same_workspace(ws_a, ws_b, 'action_organizations');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ws_action_organizations
    BEFORE INSERT OR UPDATE ON action_organizations
    FOR EACH ROW EXECUTE FUNCTION ccc_ws_action_organizations();

CREATE OR REPLACE FUNCTION ccc_ws_action_leads() RETURNS trigger AS $$
DECLARE ws_a uuid; ws_b uuid;
BEGIN
    SELECT workspace_id INTO ws_a FROM actions WHERE id = NEW.action_id;
    SELECT workspace_id INTO ws_b FROM leads WHERE id = NEW.lead_id;
    PERFORM ccc_assert_same_workspace(ws_a, ws_b, 'action_leads');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ws_action_leads
    BEFORE INSERT OR UPDATE ON action_leads
    FOR EACH ROW EXECUTE FUNCTION ccc_ws_action_leads();

-- =============================================================================
-- Constraint 5: an opportunity has exactly one matching type-detail row.
-- Fires from all three sides (opportunities, employment_opportunity_details,
-- contract_opportunity_details) so a stray detail row inserted without
-- touching the opportunities row is still caught at commit.
-- =============================================================================

CREATE OR REPLACE FUNCTION ccc_validate_opportunity_type_detail(p_opportunity_id uuid) RETURNS void AS $$
DECLARE
    v_type text;
    has_emp boolean;
    has_contract boolean;
BEGIN
    SELECT opportunity_type INTO v_type FROM opportunities WHERE id = p_opportunity_id;
    SELECT EXISTS(SELECT 1 FROM employment_opportunity_details WHERE opportunity_id = p_opportunity_id) INTO has_emp;
    SELECT EXISTS(SELECT 1 FROM contract_opportunity_details WHERE opportunity_id = p_opportunity_id) INTO has_contract;

    IF v_type = 'employment' THEN
        IF NOT has_emp OR has_contract THEN
            RAISE EXCEPTION 'opportunity % (employment) requires exactly one employment_opportunity_details row and no contract_opportunity_details row (constraint 5)', p_opportunity_id;
        END IF;
    ELSIF v_type = 'contract' THEN
        IF NOT has_contract OR has_emp THEN
            RAISE EXCEPTION 'opportunity % (contract) requires exactly one contract_opportunity_details row and no employment_opportunity_details row (constraint 5)', p_opportunity_id;
        END IF;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ccc_check_opportunity_type_detail_opp() RETURNS trigger AS $$
BEGIN
    PERFORM ccc_validate_opportunity_type_detail(NEW.id);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ccc_check_opportunity_type_detail_emp() RETURNS trigger AS $$
BEGIN
    PERFORM ccc_validate_opportunity_type_detail(NEW.opportunity_id);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ccc_check_opportunity_type_detail_contract() RETURNS trigger AS $$
BEGIN
    PERFORM ccc_validate_opportunity_type_detail(NEW.opportunity_id);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_opportunity_type_detail_opp
    AFTER INSERT OR UPDATE ON opportunities
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION ccc_check_opportunity_type_detail_opp();

CREATE CONSTRAINT TRIGGER trg_opportunity_type_detail_emp
    AFTER INSERT ON employment_opportunity_details
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION ccc_check_opportunity_type_detail_emp();

CREATE CONSTRAINT TRIGGER trg_opportunity_type_detail_contract
    AFTER INSERT ON contract_opportunity_details
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION ccc_check_opportunity_type_detail_contract();

-- =============================================================================
-- Constraints 7/8: Closed Won requires an accepted offer / executed agreement.
-- =============================================================================

CREATE OR REPLACE FUNCTION ccc_check_opportunity_closed_won() RETURNS trigger AS $$
DECLARE
    stage_outcome text;
    has_accepted_offer boolean;
    has_executed_agreement boolean;
BEGIN
    SELECT outcome INTO stage_outcome FROM pipeline_stages WHERE id = NEW.stage_id;

    IF stage_outcome = 'won' THEN
        IF NEW.opportunity_type = 'employment' THEN
            SELECT EXISTS(
                SELECT 1 FROM employment_offers WHERE opportunity_id = NEW.id AND status = 'accepted'
            ) INTO has_accepted_offer;
            IF NOT has_accepted_offer THEN
                RAISE EXCEPTION 'opportunity %: Closed Won employment requires an accepted employment_offers row (constraint 7)', NEW.id;
            END IF;
        ELSIF NEW.opportunity_type = 'contract' THEN
            SELECT EXISTS(
                SELECT 1 FROM contract_agreements WHERE opportunity_id = NEW.id AND status = 'executed'
            ) INTO has_executed_agreement;
            IF NOT has_executed_agreement THEN
                RAISE EXCEPTION 'opportunity %: Closed Won contract requires an executed contract_agreements row (constraint 8)', NEW.id;
            END IF;
        END IF;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_opportunity_closed_won
    AFTER INSERT OR UPDATE ON opportunities
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION ccc_check_opportunity_closed_won();

-- =============================================================================
-- Constraint 17: every qualification snapshot has exactly four same-lead,
-- same-workspace, same-policy-version assessments, one per BANT dimension.
-- =============================================================================

CREATE OR REPLACE FUNCTION ccc_check_snapshot_assessments_complete() RETURNS trigger AS $$
DECLARE
    snap_lead uuid;
    snap_ws uuid;
    snap_policy text;
    dim_count integer;
    bad_count integer;
    target_snapshot uuid;
BEGIN
    target_snapshot := COALESCE(NEW.snapshot_id, OLD.snapshot_id);

    SELECT lead_id, workspace_id, policy_version INTO snap_lead, snap_ws, snap_policy
    FROM lead_qualification_snapshots WHERE id = target_snapshot;

    SELECT count(DISTINCT dimension) INTO dim_count
    FROM lead_qualification_snapshot_assessments WHERE snapshot_id = target_snapshot;

    IF dim_count <> 4 THEN
        RAISE EXCEPTION 'lead_qualification_snapshot % must have exactly 4 dimension rows, found % (constraint 17)', target_snapshot, dim_count;
    END IF;

    SELECT count(*) INTO bad_count
    FROM lead_qualification_snapshot_assessments sa
    JOIN lead_qualification_assessments a ON a.id = sa.assessment_id
    WHERE sa.snapshot_id = target_snapshot
      AND (a.lead_id <> snap_lead OR a.workspace_id <> snap_ws OR a.policy_version <> snap_policy);

    IF bad_count > 0 THEN
        RAISE EXCEPTION 'lead_qualification_snapshot %: % assessment row(s) do not match the snapshot lead/workspace/policy_version (constraint 17)', target_snapshot, bad_count;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_snapshot_assessments_complete
    AFTER INSERT OR DELETE ON lead_qualification_snapshot_assessments
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION ccc_check_snapshot_assessments_complete();

-- =============================================================================
-- Constraints 22/23 (cross-row half): a snapshot's W-2 fields and any
-- attached compensation override must be consistent with its Lead's motion
-- and with a current, matching, same-Lead override.
-- =============================================================================

CREATE OR REPLACE FUNCTION ccc_check_snapshot_compensation() RETURNS trigger AS $$
DECLARE
    lead_motion text;
    ov_workspace_id uuid;
    ov_lead_id uuid;
    ov_candidate_cash numeric;
    ov_currency char(3);
    ov_expires_at timestamptz;
BEGIN
    SELECT motion INTO lead_motion FROM leads WHERE id = NEW.lead_id;

    IF lead_motion = 'contract' THEN
        IF NEW.w2_annual_cash_amount IS NOT NULL OR NEW.compensation_override_id IS NOT NULL THEN
            RAISE EXCEPTION 'snapshot %: a contract Lead snapshot cannot carry W-2 compensation fields or an override (constraint 23)', NEW.id;
        END IF;
    ELSIF lead_motion = 'w2' AND NEW.qualification_state = 'qualified' THEN
        IF NEW.w2_annual_cash_amount IS NULL THEN
            RAISE EXCEPTION 'snapshot %: a qualified W-2 Lead snapshot must bind evidence-backed annual cash and currency (constraint 23)', NEW.id;
        END IF;
    END IF;

    IF NEW.compensation_override_id IS NOT NULL THEN
        SELECT workspace_id, lead_id, candidate_annual_cash, currency, expires_at
        INTO ov_workspace_id, ov_lead_id, ov_candidate_cash, ov_currency, ov_expires_at
        FROM lead_compensation_overrides WHERE id = NEW.compensation_override_id;

        IF ov_lead_id IS DISTINCT FROM NEW.lead_id OR ov_workspace_id IS DISTINCT FROM NEW.workspace_id THEN
            RAISE EXCEPTION 'snapshot %: compensation_override % is not the same Lead/workspace (constraint 22)', NEW.id, NEW.compensation_override_id;
        END IF;
        IF ov_expires_at <= now() THEN
            RAISE EXCEPTION 'snapshot %: compensation_override % is expired (constraint 22)', NEW.id, NEW.compensation_override_id;
        END IF;
        IF EXISTS (SELECT 1 FROM lead_compensation_overrides WHERE supersedes_override_id = NEW.compensation_override_id) THEN
            RAISE EXCEPTION 'snapshot %: compensation_override % has been superseded (constraint 22)', NEW.id, NEW.compensation_override_id;
        END IF;
        IF ov_candidate_cash IS DISTINCT FROM NEW.w2_annual_cash_amount OR ov_currency IS DISTINCT FROM NEW.w2_annual_cash_currency THEN
            RAISE EXCEPTION 'snapshot %: compensation_override % candidate cash/currency does not match the snapshot (constraint 22)', NEW.id, NEW.compensation_override_id;
        END IF;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_snapshot_compensation_check
    AFTER INSERT ON lead_qualification_snapshots
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION ccc_check_snapshot_compensation();

-- =============================================================================
-- Booking proof append-only chain continuity (spec section 3 narrative,
-- supporting constraint 19/20): first observation has version 1 and no
-- predecessor; every successor increments version by one and keeps the same
-- Lead, workspace, provider, and booking identity as its named predecessor.
-- =============================================================================

CREATE OR REPLACE FUNCTION ccc_check_booking_proof_chain() RETURNS trigger AS $$
DECLARE
    pred_version integer;
    pred_identity text;
    pred_lead uuid;
    pred_ws uuid;
    pred_provider text;
BEGIN
    IF NEW.supersedes_booking_proof_id IS NULL THEN
        IF NEW.observation_version <> 1 THEN
            RAISE EXCEPTION 'booking_proof %: the root observation must have observation_version = 1', NEW.id;
        END IF;
    ELSE
        SELECT observation_version, booking_identity_digest, lead_id, workspace_id, scheduling_provider
        INTO pred_version, pred_identity, pred_lead, pred_ws, pred_provider
        FROM lead_booking_proofs WHERE id = NEW.supersedes_booking_proof_id;

        IF pred_version IS NULL THEN
            RAISE EXCEPTION 'booking_proof %: predecessor % not found', NEW.id, NEW.supersedes_booking_proof_id;
        END IF;
        IF pred_version <> NEW.observation_version - 1 THEN
            RAISE EXCEPTION 'booking_proof %: observation_version must increment by exactly one over its predecessor', NEW.id;
        END IF;
        IF pred_identity <> NEW.booking_identity_digest
           OR pred_lead <> NEW.lead_id
           OR pred_ws <> NEW.workspace_id
           OR pred_provider <> NEW.scheduling_provider THEN
            RAISE EXCEPTION 'booking_proof %: a successor must keep the same Lead, workspace, provider, and booking identity as its predecessor', NEW.id;
        END IF;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_booking_proof_chain
    AFTER INSERT ON lead_booking_proofs
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION ccc_check_booking_proof_chain();

-- =============================================================================
-- Constraint 19: every booking proof has at least one external participant.
-- =============================================================================

CREATE OR REPLACE FUNCTION ccc_check_booking_participants_external() RETURNS trigger AS $$
DECLARE
    ext_count integer;
    target_proof uuid;
BEGIN
    target_proof := COALESCE(NEW.booking_proof_id, OLD.booking_proof_id);

    SELECT count(*) INTO ext_count
    FROM lead_booking_participants
    WHERE booking_proof_id = target_proof AND is_external;

    IF ext_count < 1 THEN
        RAISE EXCEPTION 'booking_proof %: requires at least one external participant (constraint 19)', target_proof;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_booking_participants_external
    AFTER INSERT OR DELETE ON lead_booking_participants
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION ccc_check_booking_participants_external();

-- =============================================================================
-- Constraint 20 (+ brief phrasing): a conversion's snapshot and booking proof
-- belong to the same Lead+workspace as the conversion, the booking proof is
-- confirmed and not superseded, and the Lead is (already, same-transaction)
-- status = converted.
-- =============================================================================

CREATE OR REPLACE FUNCTION ccc_check_lead_conversion() RETURNS trigger AS $$
DECLARE
    snap_lead uuid;
    snap_ws uuid;
    proof_lead uuid;
    proof_ws uuid;
    proof_status text;
    proof_superseded boolean;
BEGIN
    SELECT lead_id, workspace_id INTO snap_lead, snap_ws
    FROM lead_qualification_snapshots WHERE id = NEW.qualification_snapshot_id;

    IF snap_lead IS DISTINCT FROM NEW.lead_id OR snap_ws IS DISTINCT FROM NEW.workspace_id THEN
        RAISE EXCEPTION 'lead_conversions %: qualification_snapshot % is not the same Lead/workspace (constraint 20)', NEW.id, NEW.qualification_snapshot_id;
    END IF;

    SELECT lead_id, workspace_id, event_status INTO proof_lead, proof_ws, proof_status
    FROM lead_booking_proofs WHERE id = NEW.booking_proof_id;

    IF proof_lead IS DISTINCT FROM NEW.lead_id OR proof_ws IS DISTINCT FROM NEW.workspace_id THEN
        RAISE EXCEPTION 'lead_conversions %: booking_proof % is not the same Lead/workspace (constraint 20)', NEW.id, NEW.booking_proof_id;
    END IF;
    IF proof_status <> 'confirmed' THEN
        RAISE EXCEPTION 'lead_conversions %: booking_proof % is not confirmed (status=%)', NEW.id, NEW.booking_proof_id, proof_status;
    END IF;

    SELECT EXISTS(
        SELECT 1 FROM lead_booking_proofs WHERE supersedes_booking_proof_id = NEW.booking_proof_id
    ) INTO proof_superseded;
    IF proof_superseded THEN
        RAISE EXCEPTION 'lead_conversions %: booking_proof % has been superseded', NEW.id, NEW.booking_proof_id;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM leads WHERE id = NEW.lead_id AND status = 'converted') THEN
        RAISE EXCEPTION 'lead_conversions %: lead % must be status=converted in the same transaction (constraint 2)', NEW.id, NEW.lead_id;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_lead_conversion_check
    AFTER INSERT ON lead_conversions
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION ccc_check_lead_conversion();

-- =============================================================================
-- Constraint 2 (other half): a lead marked converted must have exactly one
-- lead_conversions row (the UNIQUE(lead_id) on lead_conversions already
-- guarantees "at most one"; this guarantees "at least one").
-- =============================================================================

CREATE OR REPLACE FUNCTION ccc_check_lead_status_has_conversion() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'converted' AND NOT EXISTS (SELECT 1 FROM lead_conversions WHERE lead_id = NEW.id) THEN
        RAISE EXCEPTION 'lead %: status=converted requires a lead_conversions row in the same transaction (constraint 2)', NEW.id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_lead_status_has_conversion
    AFTER INSERT OR UPDATE OF status ON leads
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW WHEN (NEW.status = 'converted')
    EXECUTE FUNCTION ccc_check_lead_status_has_conversion();
