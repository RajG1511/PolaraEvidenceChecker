-- ============================================================
-- Evidence Quality Scores
-- Stores the output of the ML quality checker for each upload.
-- ============================================================

CREATE TABLE IF NOT EXISTS evidence_quality_scores (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- FK to whatever table stores uploaded evidence files.
    -- Replace 'evidence_uploads' with the actual table name
    -- once Surya confirms it.
    evidence_id      UUID NOT NULL
                     REFERENCES evidence_uploads(id) ON DELETE CASCADE,

    control_id       TEXT NOT NULL,                   -- e.g. "CC6.1"
    score            NUMERIC(4,3) NOT NULL             -- 0.000 – 1.000
                     CHECK (score >= 0 AND score <= 1),
    verdict          TEXT NOT NULL
                     CHECK (verdict IN ('sufficient', 'insufficient', 'uncertain')),
    explanation      TEXT NOT NULL DEFAULT '',
    missing_elements TEXT[] NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for the most common query pattern:
-- "get the latest quality score for this piece of evidence"
CREATE INDEX idx_eqs_evidence_id ON evidence_quality_scores(evidence_id);

-- Index for analytics queries:
-- "show me all insufficient scores for CC6.1"
CREATE INDEX idx_eqs_control_verdict ON evidence_quality_scores(control_id, verdict);

-- ============================================================
-- Row Level Security
-- Scopes all access to the org that owns the evidence.
-- ============================================================

ALTER TABLE evidence_quality_scores ENABLE ROW LEVEL SECURITY;

-- This policy joins through evidence_uploads to find the org_id,
-- then checks it against the JWT claim.
-- Adjust 'evidence_uploads.org_id' and the JWT path to match
-- your actual schema.
CREATE POLICY "org_isolation" ON evidence_quality_scores
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM evidence_uploads eu
            WHERE eu.id = evidence_quality_scores.evidence_id
              AND eu.org_id = (auth.jwt() ->> 'org_id')::UUID
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM evidence_uploads eu
            WHERE eu.id = evidence_quality_scores.evidence_id
              AND eu.org_id = (auth.jwt() ->> 'org_id')::UUID
        )
    );