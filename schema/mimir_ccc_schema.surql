-- ============================================================================
-- Mímir: The Grammar of Reality (v0.7.0) — SurrealDB Multi-Model Schema
-- Product: Career Command Center (CCC) / RavenmaskOS 5.1
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. NOUN ENTITIES (BE Trunk: State Payload)
-- ----------------------------------------------------------------------------

-- Organizations (Employers / Clients)
DEFINE TABLE organization SCHEMAFULL;
DEFINE FIELD name ON organization TYPE string;
DEFINE FIELD domain ON organization TYPE option<string>;
DEFINE FIELD industry ON organization TYPE option<string>;
DEFINE FIELD target_tier ON organization TYPE string 
    ASSERT $value IN ['tier_1', 'tier_2', 'tier_3', 'general'] 
    DEFAULT 'general';
DEFINE FIELD advocacy_rating ON organization TYPE float DEFAULT 0.0;
DEFINE FIELD notes ON organization TYPE option<string>;
DEFINE FIELD created_at ON organization TYPE datetime DEFAULT time::now();
DEFINE FIELD updated_at ON organization TYPE datetime DEFAULT time::now();

-- Contacts (People / Network from Dex & LinkedIn)
DEFINE TABLE contact SCHEMAFULL;
DEFINE FIELD name ON contact TYPE string;
DEFINE FIELD email ON contact TYPE option<string>;
DEFINE FIELD linkedin_url ON contact TYPE option<string>;
DEFINE FIELD headline ON contact TYPE option<string>;
DEFINE FIELD contact_role ON contact TYPE string 
    ASSERT $value IN ['champion', 'economic_buyer', 'recruiter', 'peer', 'gatekeeper', 'other']
    DEFAULT 'other';
DEFINE FIELD relationship_strength ON contact TYPE float DEFAULT 0.0;
DEFINE FIELD last_contacted_at ON contact TYPE option<datetime>;
DEFINE FIELD created_at ON contact TYPE datetime DEFAULT time::now();
DEFINE FIELD updated_at ON contact TYPE datetime DEFAULT time::now();

-- Leads (Unqualified top-of-funnel signals & job postings)
DEFINE TABLE lead SCHEMAFULL;
DEFINE FIELD source_kind ON lead TYPE string 
    ASSERT $value IN ['job_posting', 'inbound_recruiter', 'network_cluster', 'referral']
    DEFAULT 'job_posting';
DEFINE FIELD title ON lead TYPE string;
DEFINE FIELD external_url ON lead TYPE option<string>;
DEFINE FIELD description ON lead TYPE option<string>;
DEFINE FIELD salary_min ON lead TYPE option<int>;
DEFINE FIELD salary_max ON lead TYPE option<int>;
DEFINE FIELD salary_currency ON lead TYPE string DEFAULT 'USD';
DEFINE FIELD state ON lead TYPE string 
    ASSERT $value IN ['discovered', 'triaged', 'qualified', 'disqualified', 'converted'] 
    DEFAULT 'discovered';

-- BANT Qualification Payload
DEFINE FIELD bant ON lead TYPE object DEFAULT {
    budget_fit: false,
    authority_identified: false,
    need_alignment: 0.0,
    timeline: 'unknown'
};

-- Semantic Vector (768-dim) for Cosine Similarity Fit Matching against Profile
DEFINE FIELD embedding ON lead TYPE option<array<float>>;
DEFINE INDEX lead_fit_vector_idx ON lead FIELDS embedding HNSW DIMENSION 768 DIST COSINE;

DEFINE FIELD created_at ON lead TYPE datetime DEFAULT time::now();
DEFINE FIELD updated_at ON lead TYPE datetime DEFAULT time::now();

-- Opportunities (Active Pursuits / Deals)
DEFINE TABLE opportunity SCHEMAFULL;
DEFINE FIELD title ON opportunity TYPE string;
DEFINE FIELD pursuit_type ON opportunity TYPE string 
    ASSERT $value IN ['full_time_employment', 'advisory_contract', 'b2b_implementation'] 
    DEFAULT 'full_time_employment';
DEFINE FIELD stage ON opportunity TYPE string 
    ASSERT $value IN [
        '1_target',
        '2_outreach',
        '3_applied',
        '4_recruiter_screen',
        '5_hiring_manager',
        '6_technical_panel',
        '7_executive_final',
        '8_offer_negotiation',
        'closed_won',
        'closed_lost'
    ] DEFAULT '1_target';

-- MEDDPICC Scorecard Payload
DEFINE FIELD meddpicc ON opportunity TYPE object DEFAULT {
    metrics: null,
    economic_buyer: null,
    decision_criteria: null,
    decision_process: null,
    paper_process: null,
    identified_pain: null,
    champion_contact_id: null,
    competition: null
};

DEFINE FIELD fit_score ON opportunity TYPE float DEFAULT 0.0;
DEFINE FIELD target_comp_base ON opportunity TYPE option<int>;
DEFINE FIELD target_comp_total ON opportunity TYPE option<int>;
DEFINE FIELD next_step_deadline ON opportunity TYPE option<datetime>;
DEFINE FIELD created_at ON opportunity TYPE datetime DEFAULT time::now();
DEFINE FIELD updated_at ON opportunity TYPE datetime DEFAULT time::now();

-- Submissions & Applications
DEFINE TABLE submission SCHEMAFULL;
DEFINE FIELD resume_version ON submission TYPE string;
DEFINE FIELD stage_history ON submission TYPE array<object> DEFAULT [];
DEFINE FIELD interview_schedule ON submission TYPE array<object> DEFAULT [];
DEFINE FIELD debrief_notes ON submission TYPE option<string>;
DEFINE FIELD created_at ON submission TYPE datetime DEFAULT time::now();

-- ----------------------------------------------------------------------------
-- 2. HAVE TRUNK: Structural Graph Topology (8 Canonical Primitives)
-- ----------------------------------------------------------------------------

-- CONTAINS__SHARED (e.g. Organization CONTAINS Contact)
DEFINE TABLE contains_edge SCHEMAFULL TYPE RELATION;
DEFINE FIELD kind ON contains_edge TYPE string DEFAULT 'CONTAINS__SHARED';

-- DEPENDS_ON__SHARED / DEPENDS_ON__INTERNAL
DEFINE TABLE depends_on_edge SCHEMAFULL TYPE RELATION;
DEFINE FIELD kind ON depends_on_edge TYPE string DEFAULT 'DEPENDS_ON__SHARED';

-- HOSTED_ON__EXTERNAL / HOSTED_ON__INTERNAL
DEFINE TABLE hosted_on_edge SCHEMAFULL TYPE RELATION;
DEFINE FIELD kind ON hosted_on_edge TYPE string DEFAULT 'HOSTED_ON__EXTERNAL';

-- CONNECTS_TO__SHARED (e.g. Contact CONNECTS_TO Nate)
DEFINE TABLE connects_to_edge SCHEMAFULL TYPE RELATION;
DEFINE FIELD kind ON connects_to_edge TYPE string DEFAULT 'CONNECTS_TO__SHARED';

-- GOVERNS__SHARED / GOVERNS__INTERNAL
DEFINE TABLE governs_edge SCHEMAFULL TYPE RELATION;
DEFINE FIELD kind ON governs_edge TYPE string DEFAULT 'GOVERNS__SHARED';

-- DERIVED_FROM__SHARED (e.g. Opportunity DERIVED_FROM Lead)
DEFINE TABLE derived_from_edge SCHEMAFULL TYPE RELATION;
DEFINE FIELD kind ON derived_from_edge TYPE string DEFAULT 'DERIVED_FROM__SHARED';

-- DESCRIBES__INTERNAL / DESCRIBES__SHARED
DEFINE TABLE describes_edge SCHEMAFULL TYPE RELATION;
DEFINE FIELD kind ON describes_edge TYPE string DEFAULT 'DESCRIBES__INTERNAL';

-- SUPERSEDES__SHARED
DEFINE TABLE supersedes_edge SCHEMAFULL TYPE RELATION;
DEFINE FIELD kind ON supersedes_edge TYPE string DEFAULT 'SUPERSEDES__SHARED';

-- ----------------------------------------------------------------------------
-- 3. DO TRUNK: Immutable Behavioral Mutation Receipts
-- ----------------------------------------------------------------------------

DEFINE TABLE do_receipt SCHEMAFULL;
DEFINE FIELD acting_role ON do_receipt TYPE string;
DEFINE FIELD stance ON do_receipt TYPE string ASSERT $value IN ['ACT', 'REACT', 'DIRECT', 'WITNESS', 'DECLARE'];
DEFINE FIELD mode ON do_receipt TYPE string ASSERT $value IN ['CREATE', 'READ', 'UPDATE', 'DELETE', 'INITIATE', 'RESPOND', 'NOTIFY', 'TRANSITION'];
DEFINE FIELD target_entity ON do_receipt TYPE record;
DEFINE FIELD transition_id ON do_receipt TYPE option<string>;
DEFINE FIELD state_delta ON do_receipt TYPE object DEFAULT {};
DEFINE FIELD evidence_digest ON do_receipt TYPE string;
DEFINE FIELD executed_at ON do_receipt TYPE datetime DEFAULT time::now();

-- ----------------------------------------------------------------------------
-- 4. OVERLAYS: KNOW Claim Receipts & Next Best Actions
-- ----------------------------------------------------------------------------

DEFINE TABLE know_claim SCHEMAFULL;
DEFINE FIELD observer ON know_claim TYPE string;
DEFINE FIELD method ON know_claim TYPE string;
DEFINE FIELD target_ref ON know_claim TYPE string;
DEFINE FIELD weight ON know_claim TYPE float DEFAULT 1.0;
DEFINE FIELD decay_rate ON know_claim TYPE float DEFAULT 0.05;
DEFINE FIELD validity_window_seconds ON know_claim TYPE int DEFAULT 2592000; -- 30 days
DEFINE FIELD evidence_digest ON know_claim TYPE string;
DEFINE FIELD created_at ON know_claim TYPE datetime DEFAULT time::now();

-- Next Best Actions (The Ambient Accountability Firing Stream)
DEFINE TABLE next_best_action SCHEMAFULL;
DEFINE FIELD urgency ON next_best_action TYPE string 
    ASSERT $value IN ['critical', 'high', 'medium', 'low']
    DEFAULT 'medium';
DEFINE FIELD action_type ON next_best_action TYPE string 
    ASSERT $value IN [
        'recruiter_reply',
        'champion_followup',
        'interview_prep',
        'interview_debrief',
        'tofu_publish'
    ];
DEFINE FIELD target_id ON next_best_action TYPE record;
DEFINE FIELD title ON next_best_action TYPE string;
DEFINE FIELD narrative ON next_best_action TYPE string;
DEFINE FIELD payload ON next_best_action TYPE object DEFAULT {};
DEFINE FIELD status ON next_best_action TYPE string 
    ASSERT $value IN ['pending', 'executed', 'dismissed'] 
    DEFAULT 'pending';
DEFINE FIELD deadline ON next_best_action TYPE option<datetime>;
DEFINE FIELD created_at ON next_best_action TYPE datetime DEFAULT time::now();
