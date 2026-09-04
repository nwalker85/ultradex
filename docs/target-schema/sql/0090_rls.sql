-- 0090_rls.sql
-- OPTIONAL row-level security. Enables RLS on every table that carries a
-- workspace_id column, gated by current_setting('ccc.workspace_id', true).
-- Tables the spec writes WITHOUT a workspace_id column (pipeline_stages, the
-- *_source_records provenance links, and the action_* link tables) have no
-- local column to filter on and are intentionally left out; their workspace
-- scoping is enforced by the FK/trigger chain in 0011, not by RLS here.
--
-- Idempotent: safe to re-run. Does not break the smoke test: the smoke test
-- runs as the table owner (a superuser in the scratch database), and RLS
-- policies never restrict the table owner unless FORCE ROW LEVEL SECURITY is
-- also set, which this file does not set.

DO $$
DECLARE
    t text;
    tables text[] := ARRAY[
        'workspace_scope_binding_projection',
        'organizations', 'organization_domains', 'organization_aliases',
        'contacts', 'contact_channels', 'contact_organization_affiliations',
        'pipelines', 'opportunities', 'opportunity_organizations', 'opportunity_contacts',
        'opportunity_stage_history', 'employment_opportunity_details', 'contract_opportunity_details',
        'submissions', 'employment_offers', 'contract_agreements',
        'interaction_threads', 'interactions', 'interaction_contacts',
        'interaction_opportunities', 'interaction_organizations', 'calendar_events',
        'integration_accounts', 'sync_runs', 'source_records', 'source_record_versions',
        'documents', 'document_versions', 'opportunity_documents', 'submission_documents',
        'leads', 'lead_compensation_overrides', 'lead_compensation_override_evidence',
        'lead_qualification_assessments', 'lead_qualification_evidence',
        'lead_qualification_snapshots', 'lead_qualification_snapshot_assessments',
        'lead_booking_proofs', 'lead_booking_participants', 'lead_conversions',
        'opportunity_qualification', 'qualification_evidence',
        'actions', 'scoring_runs', 'action_scores', 'next_best_action'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS ccc_workspace_isolation ON %I', t);
        EXECUTE format(
            'CREATE POLICY ccc_workspace_isolation ON %I
                USING (workspace_id::text = current_setting(''ccc.workspace_id'', true))
                WITH CHECK (workspace_id::text = current_setting(''ccc.workspace_id'', true))',
            t
        );
    END LOOP;
END;
$$;
