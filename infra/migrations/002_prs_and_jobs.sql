-- 002_prs_and_jobs.sql
-- Research PRs, comments, reviews, and durable jobs
CREATE TABLE IF NOT EXISTS research_prs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    base_version_id TEXT NOT NULL,
    proposed_version_id TEXT NOT NULL,
    status TEXT NOT NULL,
    analysis_status TEXT,
    analysis_result TEXT,
    analysis_error TEXT,
    diff_summary TEXT,
    base_file_count INTEGER,
    proposed_file_count INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS pr_comments (
    id TEXT PRIMARY KEY,
    pr_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pr_reviews (
    id TEXT PRIMARY KEY,
    pr_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    verdict TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    result TEXT,
    error TEXT
);
