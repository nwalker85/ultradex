-- 0012_indexes.sql
-- Spec "Indexing baseline": B-tree on every foreign key, partial indexes for
-- non-deleted records on primary list/lookup paths, and the explicit
-- composite indexes named in that section. Unique normalized-domain and
-- contact-channel indexes are already satisfied by UNIQUE constraints in
-- 0002; the (integration_account_id, object_type, external_id_commitment)
-- index is already satisfied by a UNIQUE constraint in 0006.

-- ---------------------------------------------------------------------------
-- Foreign-key indexes (Postgres does not create these automatically).
-- ---------------------------------------------------------------------------

CREATE INDEX idx_organization_domains_org ON organization_domains (workspace_id, organization_id);
CREATE INDEX idx_organization_aliases_org ON organization_aliases (workspace_id, organization_id);
CREATE INDEX idx_contact_channels_contact ON contact_channels (workspace_id, contact_id);
CREATE INDEX idx_contact_org_affiliations_contact ON contact_organization_affiliations (workspace_id, contact_id);
CREATE INDEX idx_contact_org_affiliations_org ON contact_organization_affiliations (workspace_id, organization_id);

CREATE INDEX idx_pipeline_stages_pipeline ON pipeline_stages (pipeline_id);

CREATE INDEX idx_opportunities_pipeline ON opportunities (workspace_id, pipeline_id);
CREATE INDEX idx_opportunities_stage ON opportunities (stage_id, pipeline_id);
CREATE INDEX idx_opportunity_organizations_org ON opportunity_organizations (workspace_id, organization_id);
CREATE INDEX idx_opportunity_contacts_contact ON opportunity_contacts (workspace_id, contact_id);
CREATE INDEX idx_opportunity_stage_history_from_stage ON opportunity_stage_history (from_stage_id);
CREATE INDEX idx_opportunity_stage_history_to_stage ON opportunity_stage_history (to_stage_id);

CREATE INDEX idx_submissions_opportunity ON submissions (workspace_id, opportunity_id);
CREATE INDEX idx_employment_offers_opportunity ON employment_offers (workspace_id, opportunity_id);
CREATE INDEX idx_contract_agreements_opportunity ON contract_agreements (workspace_id, opportunity_id);

CREATE INDEX idx_interactions_thread ON interactions (workspace_id, thread_id);
CREATE INDEX idx_interaction_contacts_contact ON interaction_contacts (workspace_id, contact_id);
CREATE INDEX idx_interaction_opportunities_opportunity ON interaction_opportunities (workspace_id, opportunity_id);
CREATE INDEX idx_interaction_organizations_org ON interaction_organizations (workspace_id, organization_id);

CREATE INDEX idx_sync_runs_account ON sync_runs (workspace_id, integration_account_id);
CREATE INDEX idx_source_records_account ON source_records (workspace_id, integration_account_id);
CREATE INDEX idx_organization_source_records_record ON organization_source_records (source_record_id);
CREATE INDEX idx_contact_source_records_record ON contact_source_records (source_record_id);
CREATE INDEX idx_lead_source_records_record ON lead_source_records (source_record_id);
CREATE INDEX idx_interaction_source_records_record ON interaction_source_records (source_record_id);
CREATE INDEX idx_opportunity_source_records_record ON opportunity_source_records (source_record_id);

CREATE INDEX idx_document_versions_document ON document_versions (workspace_id, document_id);
CREATE INDEX idx_opportunity_documents_version ON opportunity_documents (document_version_id);
CREATE INDEX idx_submission_documents_submission ON submission_documents (workspace_id, submission_id);
CREATE INDEX idx_submission_documents_version ON submission_documents (document_version_id);

CREATE INDEX idx_lead_compensation_overrides_lead ON lead_compensation_overrides (workspace_id, lead_id);
CREATE INDEX idx_lead_qualification_evidence_source_record ON lead_qualification_evidence (source_record_id) WHERE source_record_id IS NOT NULL;
CREATE INDEX idx_lead_qualification_evidence_interaction ON lead_qualification_evidence (interaction_id) WHERE interaction_id IS NOT NULL;
CREATE INDEX idx_lead_qualification_evidence_document_version ON lead_qualification_evidence (document_version_id) WHERE document_version_id IS NOT NULL;
CREATE INDEX idx_lead_qualification_snapshots_lead ON lead_qualification_snapshots (workspace_id, lead_id);
CREATE INDEX idx_lead_qualification_snapshots_override ON lead_qualification_snapshots (compensation_override_id) WHERE compensation_override_id IS NOT NULL;
CREATE INDEX idx_lead_qual_snapshot_assessments_assessment ON lead_qualification_snapshot_assessments (assessment_id);
CREATE INDEX idx_lead_booking_proofs_lead ON lead_booking_proofs (workspace_id, lead_id);
CREATE INDEX idx_lead_booking_proofs_interaction ON lead_booking_proofs (workspace_id, interaction_id);
CREATE INDEX idx_lead_conversions_organization ON lead_conversions (workspace_id, organization_id);
CREATE INDEX idx_lead_conversions_contact ON lead_conversions (workspace_id, contact_id);
CREATE INDEX idx_lead_conversions_opportunity ON lead_conversions (workspace_id, opportunity_id);

CREATE INDEX idx_qualification_evidence_qualification ON qualification_evidence (workspace_id, qualification_id);
CREATE INDEX idx_qualification_evidence_interaction ON qualification_evidence (interaction_id) WHERE interaction_id IS NOT NULL;
CREATE INDEX idx_qualification_evidence_document_version ON qualification_evidence (document_version_id) WHERE document_version_id IS NOT NULL;
CREATE INDEX idx_qualification_evidence_contact ON qualification_evidence (contact_id) WHERE contact_id IS NOT NULL;

CREATE INDEX idx_action_opportunities_opportunity ON action_opportunities (opportunity_id);
CREATE INDEX idx_action_contacts_contact ON action_contacts (contact_id);
CREATE INDEX idx_action_organizations_organization ON action_organizations (organization_id);
CREATE INDEX idx_action_leads_lead ON action_leads (lead_id);
CREATE INDEX idx_action_scores_scoring_run ON action_scores (workspace_id, scoring_run_id);
CREATE INDEX idx_next_best_action_scoring_run ON next_best_action (scoring_run_id) WHERE scoring_run_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Explicit composite indexes named in "Indexing baseline".
-- ---------------------------------------------------------------------------

CREATE INDEX idx_opportunities_stage_close ON opportunities (workspace_id, stage_id, expected_close_date);
CREATE INDEX idx_opportunity_stage_history_changed ON opportunity_stage_history (opportunity_id, changed_at DESC);
CREATE INDEX idx_interactions_occurred ON interactions (workspace_id, occurred_at DESC);
CREATE INDEX idx_source_record_versions_observed ON source_record_versions (source_record_id, observed_at DESC);
CREATE INDEX idx_actions_status_due ON actions (workspace_id, status, due_at);
CREATE INDEX idx_action_scores_scored ON action_scores (action_id, scored_at DESC);
CREATE INDEX idx_lead_qualification_assessments_assessed ON lead_qualification_assessments (lead_id, dimension, assessed_at DESC);
CREATE INDEX idx_lead_qualification_evidence_observed ON lead_qualification_evidence (assessment_id, observed_at DESC);
CREATE INDEX idx_lead_qualification_snapshots_created ON lead_qualification_snapshots (lead_id, created_at DESC);
CREATE INDEX idx_lead_booking_proofs_observed ON lead_booking_proofs (lead_id, observed_at DESC);
CREATE INDEX idx_lead_compensation_overrides_approved ON lead_compensation_overrides (lead_id, approved_at DESC);

-- ---------------------------------------------------------------------------
-- Partial indexes for non-deleted records on primary list/lookup paths.
-- ---------------------------------------------------------------------------

CREATE INDEX idx_organizations_workspace_active ON organizations (workspace_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_contacts_workspace_active ON contacts (workspace_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_leads_workspace_active ON leads (workspace_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_opportunities_workspace_active ON opportunities (workspace_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_documents_workspace_active ON documents (workspace_id) WHERE deleted_at IS NULL;
