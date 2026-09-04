-- 0007_documents.sql
-- Spec section 9 "Documents and immutable versions".

-- ---------------------------------------------------------------------------
-- documents
-- ---------------------------------------------------------------------------
CREATE TABLE documents (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     uuid NOT NULL REFERENCES workspaces (id),
    document_type    text NOT NULL,
    name             text NOT NULL,
    status           text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    deleted_at       timestamptz NULL,

    CONSTRAINT documents_type_chk
        CHECK (document_type IN ('resume', 'cover_letter', 'job_description', 'offer', 'contract', 'sow', 'other')),
    CONSTRAINT documents_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE documents IS
    'Spec section 9: a logical document; its content lives in versions.';

CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION ccc_set_updated_at();

-- ---------------------------------------------------------------------------
-- document_versions (append-only; trigger added in 0011)
-- ---------------------------------------------------------------------------
CREATE TABLE document_versions (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      uuid NOT NULL REFERENCES workspaces (id),
    document_id       uuid NOT NULL,
    version_number    integer NOT NULL,
    storage_key       text NOT NULL,
    media_type        text NOT NULL,
    sha256            text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT document_versions_document_fk
        FOREIGN KEY (workspace_id, document_id)
        REFERENCES documents (workspace_id, id),
    CONSTRAINT document_versions_document_version_uq UNIQUE (document_id, version_number),
    CONSTRAINT document_versions_workspace_sha256_uq UNIQUE (workspace_id, sha256),
    CONSTRAINT document_versions_workspace_id_unique UNIQUE (workspace_id, id)
);

COMMENT ON TABLE document_versions IS
    'Spec section 9 + constraint 9/10: immutable content version; submissions reference these, not documents.';

-- ---------------------------------------------------------------------------
-- opportunity_documents
-- ---------------------------------------------------------------------------
CREATE TABLE opportunity_documents (
    workspace_id           uuid NOT NULL REFERENCES workspaces (id),
    opportunity_id         uuid NOT NULL,
    document_version_id    uuid NOT NULL,
    role                   text NOT NULL,

    PRIMARY KEY (opportunity_id, document_version_id, role),
    CONSTRAINT opportunity_documents_opp_fk
        FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES opportunities (workspace_id, id),
    CONSTRAINT opportunity_documents_version_fk
        FOREIGN KEY (workspace_id, document_version_id)
        REFERENCES document_versions (workspace_id, id)
);

COMMENT ON TABLE opportunity_documents IS
    'Spec section 9: document versions attached to an opportunity in a given role.';

-- ---------------------------------------------------------------------------
-- submission_documents
-- ---------------------------------------------------------------------------
CREATE TABLE submission_documents (
    workspace_id           uuid NOT NULL REFERENCES workspaces (id),
    submission_id          uuid NOT NULL,
    document_version_id    uuid NOT NULL,
    role                   text NOT NULL,

    PRIMARY KEY (submission_id, document_version_id, role),
    CONSTRAINT submission_documents_submission_fk
        FOREIGN KEY (workspace_id, submission_id)
        REFERENCES submissions (workspace_id, id),
    CONSTRAINT submission_documents_version_fk
        FOREIGN KEY (workspace_id, document_version_id)
        REFERENCES document_versions (workspace_id, id)
);

COMMENT ON TABLE submission_documents IS
    'Spec section 9 + constraint 10: submitted artifacts reference immutable document versions.';
