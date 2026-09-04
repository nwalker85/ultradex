-- 9000_smoke_roundtrip.sql
-- Acceptance script: positive lead -> conversion -> opportunity round trip in
-- one transaction, then eight negative checks each in their own DO block
-- (SET CONSTRAINTS ALL IMMEDIATE is used where the violated rule lives in a
-- DEFERRABLE INITIALLY DEFERRED constraint trigger from 0011).
--
-- Run with: psql -v ON_ERROR_STOP=1 -f 9000_smoke_roundtrip.sql
-- (NOT --single-transaction: this file manages its own transaction
-- boundaries so the positive path commits before the negative checks run.)

-- =============================================================================
-- 1. Positive path
-- =============================================================================

BEGIN;

DO $$
DECLARE
    v_workspace_id      uuid;
    v_pipeline_id        uuid;
    v_stage_new           uuid;
    v_org_id               uuid;
    v_contact_id            uuid;
    v_ia_id                  uuid;
    v_sr_id                   uuid;
    v_lead_id                  uuid;
    v_assess_budget              uuid;
    v_assess_authority            uuid;
    v_assess_need                  uuid;
    v_assess_timeline                uuid;
    v_snapshot_id                     uuid;
    v_interaction_id                    uuid;
    v_proof_id                            uuid;
    v_opp_id                                uuid;
    v_action_id                               uuid;
    v_scoring_run_id                            uuid;
BEGIN
    -- workspace
    INSERT INTO workspaces (name) VALUES ('Smoke Workspace') RETURNING id INTO v_workspace_id;

    -- resolved scope-binding projection (Mimir-owned cache; ADR-0002 section 4 columns)
    INSERT INTO workspace_scope_binding_projection (
        workspace_id, projection_status, tenant_id, organization_id, application_id, project_id, scope_key,
        mapping_version, registry_revision, resolver_version, lineage_ref,
        effective_at, resolved_at, expires_at, freshness
    ) VALUES (
        v_workspace_id, 'resolved', 'ravenhelm', 'ravenhelm', 'ccc', 'smoke-workspace',
        'i/ravenhelm/t/ravenhelm/o/ravenhelm/a/ccc/p/smoke-workspace',
        'v1', 'rev-1', 'resolver-v1', 'lineage-binding-1',
        now(), now(), now() + interval '1 year', 'current'
    );

    -- seed the shared career pipeline
    v_pipeline_id := ccc_seed_career_pipeline(v_workspace_id);
    SELECT id INTO v_stage_new FROM pipeline_stages WHERE pipeline_id = v_pipeline_id AND ordinal = 1;

    -- resolved organization projection
    INSERT INTO organizations (
        workspace_id, mimir_entity_id, resolution_status, resolution_id, mimir_entity_version,
        tenant_mapping_version, registry_revision, resolver_version, policy_version,
        resolution_lineage_ref, source_event_position, resolution_expires_at, resolution_freshness,
        mimir_scope_key, display_name, kind, resolved_at
    ) VALUES (
        v_workspace_id, 'organization:company:' || gen_random_uuid(), 'resolved', 'res-org-1', 1,
        'v1', 'rev-1', 'resolver-v1', 'policy-v1',
        'lineage-org-1', 'pos-1', now() + interval '1 year', 'current',
        'i/ravenhelm', 'Smoke Org', 'company', now()
    ) RETURNING id INTO v_org_id;

    -- resolved contact projection
    INSERT INTO contacts (
        workspace_id, mimir_entity_id, resolution_status, resolution_id, mimir_entity_version,
        tenant_mapping_version, registry_revision, resolver_version, policy_version,
        resolution_lineage_ref, source_event_position, resolution_expires_at, resolution_freshness,
        mimir_scope_key, display_name, resolved_at
    ) VALUES (
        v_workspace_id, 'person:contact:' || gen_random_uuid(), 'resolved', 'res-contact-1', 1,
        'v1', 'rev-1', 'resolver-v1', 'policy-v1',
        'lineage-contact-1', 'pos-2', now() + interval '1 year', 'current',
        'i/ravenhelm/t/ravenhelm/o/ravenhelm', 'Smoke Contact', now()
    ) RETURNING id INTO v_contact_id;

    -- affiliation
    INSERT INTO contact_organization_affiliations (workspace_id, contact_id, organization_id, title, is_current)
    VALUES (v_workspace_id, v_contact_id, v_org_id, 'Smoke Title', true);

    -- integration provenance chain
    INSERT INTO integration_accounts (workspace_id, provider, external_account_ref, external_account_commitment, status)
    VALUES (v_workspace_id, 'dex', 'ext-acct-1', 'commit-acct-1', 'active')
    RETURNING id INTO v_ia_id;

    INSERT INTO source_records (workspace_id, integration_account_id, object_type, external_object_ref, external_id_commitment, first_seen_at, last_seen_at)
    VALUES (v_workspace_id, v_ia_id, 'linkedin_organization', 'ext-obj-1', 'commit-obj-1', now(), now())
    RETURNING id INTO v_sr_id;

    INSERT INTO source_record_versions (workspace_id, source_record_id, content_fingerprint, observed_at)
    VALUES (v_workspace_id, v_sr_id, 'fingerprint-1', now());

    INSERT INTO organization_source_records (organization_id, source_record_id) VALUES (v_org_id, v_sr_id);

    -- lead (motion contract)
    INSERT INTO leads (workspace_id, status, motion, title, source_type, source_commitment, discovered_at)
    VALUES (v_workspace_id, 'new', 'contract', 'Smoke Lead', 'referral', 'commit-lead-1', now())
    RETURNING id INTO v_lead_id;

    -- 4 BANT assessments (validated), each with one evidence row
    INSERT INTO lead_qualification_assessments (workspace_id, lead_id, dimension, assessment, policy_version, assessed_at, assessor_type)
    VALUES (v_workspace_id, v_lead_id, 'budget', 'validated', 'policy-v1', now(), 'operator')
    RETURNING id INTO v_assess_budget;
    INSERT INTO lead_qualification_evidence (workspace_id, assessment_id, evidence_type, content_ref, content_commitment, observed_at)
    VALUES (v_workspace_id, v_assess_budget, 'content_ref', 'ref-budget', 'commit-ev-budget', now());

    INSERT INTO lead_qualification_assessments (workspace_id, lead_id, dimension, assessment, policy_version, assessed_at, assessor_type)
    VALUES (v_workspace_id, v_lead_id, 'authority', 'validated', 'policy-v1', now(), 'operator')
    RETURNING id INTO v_assess_authority;
    INSERT INTO lead_qualification_evidence (workspace_id, assessment_id, evidence_type, content_ref, content_commitment, observed_at)
    VALUES (v_workspace_id, v_assess_authority, 'content_ref', 'ref-authority', 'commit-ev-authority', now());

    INSERT INTO lead_qualification_assessments (workspace_id, lead_id, dimension, assessment, policy_version, assessed_at, assessor_type)
    VALUES (v_workspace_id, v_lead_id, 'need', 'validated', 'policy-v1', now(), 'operator')
    RETURNING id INTO v_assess_need;
    INSERT INTO lead_qualification_evidence (workspace_id, assessment_id, evidence_type, content_ref, content_commitment, observed_at)
    VALUES (v_workspace_id, v_assess_need, 'content_ref', 'ref-need', 'commit-ev-need', now());

    INSERT INTO lead_qualification_assessments (workspace_id, lead_id, dimension, assessment, policy_version, assessed_at, assessor_type)
    VALUES (v_workspace_id, v_lead_id, 'timeline', 'validated', 'policy-v1', now(), 'operator')
    RETURNING id INTO v_assess_timeline;
    INSERT INTO lead_qualification_evidence (workspace_id, assessment_id, evidence_type, content_ref, content_commitment, observed_at)
    VALUES (v_workspace_id, v_assess_timeline, 'content_ref', 'ref-timeline', 'commit-ev-timeline', now());

    -- snapshot with 4 child rows (contract Lead => W-2 fields null)
    INSERT INTO lead_qualification_snapshots (workspace_id, lead_id, policy_version, qualification_state, snapshot_digest)
    VALUES (v_workspace_id, v_lead_id, 'policy-v1', 'qualified', 'digest-snap-1')
    RETURNING id INTO v_snapshot_id;

    INSERT INTO lead_qualification_snapshot_assessments (workspace_id, snapshot_id, dimension, assessment_id)
    VALUES
        (v_workspace_id, v_snapshot_id, 'budget', v_assess_budget),
        (v_workspace_id, v_snapshot_id, 'authority', v_assess_authority),
        (v_workspace_id, v_snapshot_id, 'need', v_assess_need),
        (v_workspace_id, v_snapshot_id, 'timeline', v_assess_timeline);

    -- confirmed booking proof (v1, no predecessor) + its interaction + one external participant
    INSERT INTO interactions (workspace_id, interaction_type, occurred_at)
    VALUES (v_workspace_id, 'meeting', now())
    RETURNING id INTO v_interaction_id;

    INSERT INTO lead_booking_proofs (
        workspace_id, lead_id, interaction_id, scheduling_provider, provider_event_ref, provider_event_commitment,
        booking_identity_digest, observation_fingerprint, observation_version, event_status,
        starts_at, ends_at, observed_at, proof_digest
    ) VALUES (
        v_workspace_id, v_lead_id, v_interaction_id, 'calendly', 'prov-evt-1', 'commit-evt-1',
        'identity-digest-1', 'fingerprint-1', 1, 'confirmed',
        now(), now() + interval '30 minutes', now(), 'proof-digest-1'
    ) RETURNING id INTO v_proof_id;

    INSERT INTO lead_booking_participants (workspace_id, booking_proof_id, participant_ref, participant_commitment, is_external)
    VALUES (v_workspace_id, v_proof_id, 'participant-1', 'commit-participant-1', true);

    -- opportunity (contract) in the seeded pipeline at the first stage
    INSERT INTO opportunities (workspace_id, pipeline_id, stage_id, opportunity_type, name, opened_at)
    VALUES (v_workspace_id, v_pipeline_id, v_stage_new, 'contract', 'Smoke Opportunity', now())
    RETURNING id INTO v_opp_id;

    INSERT INTO contract_opportunity_details (opportunity_id, workspace_id, engagement_model)
    VALUES (v_opp_id, v_workspace_id, 'direct');

    INSERT INTO opportunity_stage_history (workspace_id, opportunity_id, from_stage_id, to_stage_id, changed_at)
    VALUES (v_workspace_id, v_opp_id, NULL, v_stage_new, now());

    INSERT INTO opportunity_organizations (workspace_id, opportunity_id, organization_id, role, is_primary)
    VALUES (v_workspace_id, v_opp_id, v_org_id, 'client', true);

    INSERT INTO opportunity_contacts (workspace_id, opportunity_id, contact_id, role)
    VALUES (v_workspace_id, v_opp_id, v_contact_id, 'decision_maker');

    -- lead conversion (atomic: status transition + conversion row)
    UPDATE leads SET status = 'converted' WHERE id = v_lead_id;

    INSERT INTO lead_conversions (
        workspace_id, lead_id, qualification_snapshot_id, booking_proof_id,
        organization_id, contact_id, opportunity_id, converted_at
    ) VALUES (
        v_workspace_id, v_lead_id, v_snapshot_id, v_proof_id,
        v_org_id, v_contact_id, v_opp_id, now()
    );

    -- action + action_lead + scoring_run + action_score + next_best_action
    INSERT INTO actions (workspace_id, action_type, status, title)
    VALUES (v_workspace_id, 'follow_up', 'proposed', 'Smoke Action')
    RETURNING id INTO v_action_id;

    INSERT INTO action_leads (action_id, lead_id) VALUES (v_action_id, v_lead_id);

    INSERT INTO scoring_runs (workspace_id, model_name, model_version, started_at)
    VALUES (v_workspace_id, 'smoke-model', 'v1', now())
    RETURNING id INTO v_scoring_run_id;

    INSERT INTO action_scores (workspace_id, action_id, scoring_run_id, total_score, score_components, scored_at)
    VALUES (v_workspace_id, v_action_id, v_scoring_run_id, 0.9, '{}'::jsonb, now());

    INSERT INTO next_best_action (workspace_id, action_id, selected_at, scoring_run_id)
    VALUES (v_workspace_id, v_action_id, now(), v_scoring_run_id);
END;
$$;

COMMIT;

-- Round-trip proof: lead.status = 'converted' and lead_conversions joins to the opportunity.
DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count
    FROM lead_conversions lc
    JOIN leads l ON l.id = lc.lead_id AND l.status = 'converted'
    JOIN opportunities o ON o.id = lc.opportunity_id
    WHERE l.title = 'Smoke Lead' AND o.name = 'Smoke Opportunity';

    IF v_count <> 1 THEN
        RAISE EXCEPTION 'round-trip verification FAILED: expected 1 converted-lead -> opportunity link via lead_conversions, found %', v_count;
    END IF;
    RAISE NOTICE 'round-trip verified: lead.status=converted and lead_conversions joins to its opportunity';
END;
$$;

-- =============================================================================
-- 2. Negative checks
-- =============================================================================

-- Negative check 1: cross-workspace FK (contact from workspace B on opportunity of workspace A).
DO $$
DECLARE
    v_ws_a uuid;
    v_ws_b uuid;
    v_opp_a uuid;
    v_contact_b uuid;
BEGIN
    SELECT id INTO v_ws_a FROM workspaces WHERE name = 'Smoke Workspace';
    SELECT id INTO v_opp_a FROM opportunities WHERE name = 'Smoke Opportunity';

    INSERT INTO workspaces (name) VALUES ('Smoke Workspace B') RETURNING id INTO v_ws_b;
    INSERT INTO contacts (workspace_id, resolution_status, display_name)
    VALUES (v_ws_b, 'unresolved', 'Smoke Contact B')
    RETURNING id INTO v_contact_b;

    INSERT INTO opportunity_contacts (workspace_id, opportunity_id, contact_id, role)
    VALUES (v_ws_a, v_opp_a, v_contact_b, 'recruiter');

    RAISE EXCEPTION 'negative check 1 FAILED: cross-workspace opportunity_contacts insert should have been rejected';
EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'negative check 1 FAILED%' THEN
        RAISE;
    END IF;
    RAISE NOTICE 'negative check 1 passed (%): %', SQLSTATE, SQLERRM;
END;
$$;

-- Negative check 2: second (wrong-type) detail row for the contract opportunity.
DO $$
DECLARE
    v_ws uuid;
    v_opp uuid;
BEGIN
    SELECT id INTO v_ws FROM workspaces WHERE name = 'Smoke Workspace';
    SELECT id INTO v_opp FROM opportunities WHERE name = 'Smoke Opportunity';

    INSERT INTO employment_opportunity_details (opportunity_id, workspace_id, employment_type)
    VALUES (v_opp, v_ws, 'full_time');

    SET CONSTRAINTS ALL IMMEDIATE;

    RAISE EXCEPTION 'negative check 2 FAILED: wrong-type detail row should have been rejected';
EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'negative check 2 FAILED%' THEN
        RAISE;
    END IF;
    RAISE NOTICE 'negative check 2 passed (%): %', SQLSTATE, SQLERRM;
END;
$$;

-- Negative check 3: move the contract opportunity to Closed Won without an executed agreement.
DO $$
DECLARE
    v_opp uuid;
    v_pipeline uuid;
    v_stage_won uuid;
BEGIN
    SELECT id INTO v_opp FROM opportunities WHERE name = 'Smoke Opportunity';
    SELECT pipeline_id INTO v_pipeline FROM opportunities WHERE id = v_opp;
    SELECT id INTO v_stage_won FROM pipeline_stages WHERE pipeline_id = v_pipeline AND code = 'closed_won';

    UPDATE opportunities SET stage_id = v_stage_won WHERE id = v_opp;

    SET CONSTRAINTS ALL IMMEDIATE;

    RAISE EXCEPTION 'negative check 3 FAILED: contract opportunity moved to Closed Won without an executed agreement should have been rejected';
EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'negative check 3 FAILED%' THEN
        RAISE;
    END IF;
    RAISE NOTICE 'negative check 3 passed (%): %', SQLSTATE, SQLERRM;
END;
$$;

-- Negative check 4: UPDATE on opportunity_stage_history rejected (append-only).
DO $$
DECLARE
    v_history_id uuid;
BEGIN
    SELECT id INTO v_history_id FROM opportunity_stage_history
    WHERE opportunity_id = (SELECT id FROM opportunities WHERE name = 'Smoke Opportunity')
    LIMIT 1;

    UPDATE opportunity_stage_history SET reason = 'hacked' WHERE id = v_history_id;

    RAISE EXCEPTION 'negative check 4 FAILED: UPDATE on append-only opportunity_stage_history should have been rejected';
EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'negative check 4 FAILED%' THEN
        RAISE;
    END IF;
    RAISE NOTICE 'negative check 4 passed (%): %', SQLSTATE, SQLERRM;
END;
$$;

-- Negative check 5: second next_best_action for the same workspace rejected.
DO $$
DECLARE
    v_ws uuid;
    v_action uuid;
BEGIN
    SELECT id INTO v_ws FROM workspaces WHERE name = 'Smoke Workspace';
    SELECT id INTO v_action FROM actions WHERE title = 'Smoke Action';

    INSERT INTO next_best_action (workspace_id, action_id, selected_at)
    VALUES (v_ws, v_action, now());

    RAISE EXCEPTION 'negative check 5 FAILED: second next_best_action for the same workspace should have been rejected';
EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'negative check 5 FAILED%' THEN
        RAISE;
    END IF;
    RAISE NOTICE 'negative check 5 passed (%): %', SQLSTATE, SQLERRM;
END;
$$;

-- Negative check 6: conversion referencing a snapshot of a different lead rejected.
DO $$
DECLARE
    v_ws uuid;
    v_org uuid;
    v_contact uuid;
    v_opp uuid;
    v_lead_y uuid;
    v_lead_x uuid;
    v_snapshot_y uuid;
    v_interaction_x uuid;
    v_proof_x uuid;
BEGIN
    SELECT id INTO v_ws FROM workspaces WHERE name = 'Smoke Workspace';
    SELECT id INTO v_org FROM organizations WHERE display_name = 'Smoke Org';
    SELECT id INTO v_contact FROM contacts WHERE display_name = 'Smoke Contact';
    SELECT id INTO v_opp FROM opportunities WHERE name = 'Smoke Opportunity';

    INSERT INTO leads (workspace_id, status, motion, title, source_type, source_commitment, discovered_at)
    VALUES (v_ws, 'new', 'contract', 'Smoke Lead Y', 'referral', 'commit-lead-y', now())
    RETURNING id INTO v_lead_y;

    INSERT INTO lead_qualification_snapshots (workspace_id, lead_id, policy_version, qualification_state, snapshot_digest)
    VALUES (v_ws, v_lead_y, 'policy-v1', 'nurturing', 'digest-snap-y')
    RETURNING id INTO v_snapshot_y;

    INSERT INTO leads (workspace_id, status, motion, title, source_type, source_commitment, discovered_at)
    VALUES (v_ws, 'new', 'contract', 'Smoke Lead X', 'referral', 'commit-lead-x', now())
    RETURNING id INTO v_lead_x;

    INSERT INTO interactions (workspace_id, interaction_type, occurred_at)
    VALUES (v_ws, 'meeting', now())
    RETURNING id INTO v_interaction_x;

    INSERT INTO lead_booking_proofs (
        workspace_id, lead_id, interaction_id, scheduling_provider, provider_event_ref, provider_event_commitment,
        booking_identity_digest, observation_fingerprint, observation_version, event_status,
        starts_at, ends_at, observed_at, proof_digest
    ) VALUES (
        v_ws, v_lead_x, v_interaction_x, 'calendly', 'prov-evt-x', 'commit-evt-x',
        'identity-digest-x', 'fingerprint-x', 1, 'confirmed',
        now(), now() + interval '30 minutes', now(), 'proof-digest-x'
    ) RETURNING id INTO v_proof_x;

    INSERT INTO lead_booking_participants (workspace_id, booking_proof_id, participant_ref, participant_commitment, is_external)
    VALUES (v_ws, v_proof_x, 'participant-x', 'commit-participant-x', true);

    UPDATE leads SET status = 'converted' WHERE id = v_lead_x;

    -- Violation: qualification_snapshot_id (v_snapshot_y) belongs to lead Y, not lead X.
    INSERT INTO lead_conversions (
        workspace_id, lead_id, qualification_snapshot_id, booking_proof_id,
        organization_id, contact_id, opportunity_id, converted_at
    ) VALUES (
        v_ws, v_lead_x, v_snapshot_y, v_proof_x, v_org, v_contact, v_opp, now()
    );

    SET CONSTRAINTS ALL IMMEDIATE;

    RAISE EXCEPTION 'negative check 6 FAILED: conversion referencing a different lead''s snapshot should have been rejected';
EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'negative check 6 FAILED%' THEN
        RAISE;
    END IF;
    RAISE NOTICE 'negative check 6 passed (%): %', SQLSTATE, SQLERRM;
END;
$$;

-- Negative check 7: resolved contact with null mimir_entity_id rejected.
DO $$
DECLARE
    v_ws uuid;
BEGIN
    SELECT id INTO v_ws FROM workspaces WHERE name = 'Smoke Workspace';

    INSERT INTO contacts (workspace_id, resolution_status, display_name, mimir_entity_id)
    VALUES (v_ws, 'resolved', 'Smoke Bad Contact', NULL);

    RAISE EXCEPTION 'negative check 7 FAILED: resolved contact with null mimir_entity_id should have been rejected';
EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'negative check 7 FAILED%' THEN
        RAISE;
    END IF;
    RAISE NOTICE 'negative check 7 passed (%): %', SQLSTATE, SQLERRM;
END;
$$;

-- Negative check 8: unresolved contact with a coordinate rejected.
DO $$
DECLARE
    v_ws uuid;
BEGIN
    SELECT id INTO v_ws FROM workspaces WHERE name = 'Smoke Workspace';

    INSERT INTO contacts (workspace_id, resolution_status, display_name, mimir_entity_id, mimir_scope_key)
    VALUES (v_ws, 'unresolved', 'Smoke Bad Contact 2', 'person:contact:' || gen_random_uuid(), 'i/ravenhelm');

    RAISE EXCEPTION 'negative check 8 FAILED: unresolved contact with a coordinate should have been rejected';
EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'negative check 8 FAILED%' THEN
        RAISE;
    END IF;
    RAISE NOTICE 'negative check 8 passed (%): %', SQLSTATE, SQLERRM;
END;
$$;

-- =============================================================================
-- 3. Final summary
-- =============================================================================

DO $$
DECLARE
    v_table_count integer;
BEGIN
    SELECT count(*) INTO v_table_count
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

    RAISE NOTICE 'SMOKE OK: % tables, % negative checks passed', v_table_count, 8;
END;
$$;
