-- 0013_seed_pipeline.sql
-- Spec section 4: "Career Command Center seeds one shared career-opportunity
-- pipeline. Both opportunity types reference it." Stage codes/names/ordinals
-- below are placeholders only -- the spec's explicit non-goals list "exact
-- stage names or probability values" as out of scope for this design; the
-- product/UX layer owns the real taxonomy.

CREATE OR REPLACE FUNCTION ccc_seed_career_pipeline(p_workspace_id uuid)
RETURNS uuid AS $$
DECLARE
    v_pipeline_id uuid;
BEGIN
    INSERT INTO pipelines (workspace_id, code, name)
    VALUES (p_workspace_id, 'career', 'Career Pipeline (placeholder name)')
    ON CONFLICT (workspace_id, code) DO UPDATE SET name = EXCLUDED.name
    RETURNING id INTO v_pipeline_id;

    INSERT INTO pipeline_stages (pipeline_id, code, name, ordinal, outcome)
    VALUES
        (v_pipeline_id, 'new',           'New (placeholder)',                    1, NULL),
        (v_pipeline_id, 'contacted',     'Contacted (placeholder)',              2, NULL),
        (v_pipeline_id, 'qualifying',    'Qualifying (placeholder)',             3, NULL),
        (v_pipeline_id, 'submitted',     'Submitted (placeholder)',              4, NULL),
        (v_pipeline_id, 'interviewing',  'Interviewing (placeholder)',           5, NULL),
        (v_pipeline_id, 'offer',         'Offer / Negotiation (placeholder)',    6, NULL),
        (v_pipeline_id, 'closed_won',    'Closed Won (placeholder)',             7, 'won'),
        (v_pipeline_id, 'closed_lost',   'Closed Lost (placeholder)',            8, 'lost')
    ON CONFLICT (pipeline_id, code) DO NOTHING;

    RETURN v_pipeline_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION ccc_seed_career_pipeline(uuid) IS
    'Spec section 4: seeds the one shared career pipeline for a workspace with placeholder ordered stages, including two terminal outcome stages.';
