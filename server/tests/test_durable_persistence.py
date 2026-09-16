"""
test_durable_persistence.py — In-memory persistence tests.
Verifies that Research PRs, comments, reviews, jobs, and evidence domain records
are correctly handled by the stateless in-memory provider.
"""
import pytest

from server.domain.auth_models import (
    Comment,
    DiffHunk,
    DiffSummary,
    FileDiff,
    PRStatus,
    ResearchPR,
    Review,
)
from server.domain.models import (
    Evidence,
    EvidenceType,
    ImpactFinding,
    JobRecord,
    JobStatus,
    RelationshipType,
    VerificationStatus,
)
from server.engine.persistence.db_adapter import InMemoryAdapter


@pytest.mark.asyncio
async def test_pr_comments_and_reviews_in_memory():
    """
    Research PRs, comments, and reviews operations in InMemoryAdapter.
    """
    adapter = InMemoryAdapter()

    diff = DiffSummary(
        description="Fix learning rate decay",
        total_files_changed=1,
        total_additions=3,
        total_deletions=1,
        modified=[
            FileDiff(
                path="train.py",
                status="modified",
                additions=3,
                deletions=1,
                hunks=[
                    DiffHunk(
                        old_start=10, old_lines=5, new_start=10, new_lines=7,
                        header="@@ -10,5 +10,7 @@",
                        lines=["- lr = 0.1", "+ lr = 0.01"]
                    )
                ]
            )
        ]
    )

    pr = ResearchPR(
        id="pr_test_1",
        project_id="proj_1",
        author_id="usr_1",
        base_version_id="main",
        proposed_version_id="fix-lr",
        status=PRStatus.OPEN,
        analysis_status="COMPLETE",
        analysis_result={"status": "VERIFIED"},
        diff_summary=diff,
        base_file_count=10,
        proposed_file_count=10,
        created_at="2026-09-14T10:00:00Z"
    )
    await adapter.create_pr(pr)

    comment = Comment(
        id="comm_1",
        pr_id="pr_test_1",
        author_id="usr_2",
        content="Checked the formula, looks accurate.",
        created_at="2026-09-14T10:05:00Z"
    )
    await adapter.add_comment(comment)

    review = Review(
        id="rev_1",
        pr_id="pr_test_1",
        reviewer_id="usr_reviewer",
        verdict=PRStatus.APPROVED,
        content="Approved after verification.",
        created_at="2026-09-14T10:10:00Z"
    )
    await adapter.add_review(review)

    loaded_pr = await adapter.get_pr("pr_test_1")
    assert loaded_pr is not None
    assert loaded_pr.id == "pr_test_1"
    assert loaded_pr.project_id == "proj_1"
    assert loaded_pr.analysis_status == "COMPLETE"
    assert loaded_pr.analysis_result == {"status": "VERIFIED"}
    total_changed = loaded_pr.diff_summary.total_files_changed if hasattr(loaded_pr.diff_summary, "total_files_changed") else loaded_pr.diff_summary["total_files_changed"]
    assert total_changed == 1

    loaded_comments = await adapter.get_comments("pr_test_1")
    assert len(loaded_comments) == 1
    assert loaded_comments[0].content == "Checked the formula, looks accurate."

    loaded_reviews = await adapter.get_reviews("pr_test_1")
    assert len(loaded_reviews) == 1
    assert loaded_reviews[0].verdict == PRStatus.APPROVED


@pytest.mark.asyncio
async def test_jobs_in_memory():
    """
    Job state and progress handling in InMemoryAdapter.
    """
    adapter = InMemoryAdapter()
    job = JobRecord(
        jobId="job_abc123",
        status=JobStatus.PROCESSING,
        result={"_progress": "stage:parse_paper"},
        createdAt="2026-09-14T12:00:00Z",
        updatedAt="2026-09-14T12:00:10Z"
    )
    await adapter.create_job_record(job)

    recovered_job = await adapter.get_job_record("job_abc123")
    assert recovered_job is not None
    assert recovered_job.status == JobStatus.PROCESSING
    assert recovered_job.result.get("_progress") == "stage:parse_paper"

    # Update status
    await adapter.update_job_record("job_abc123", JobStatus.READY, result={"overall": "OK"})

    final_job = await adapter.get_job_record("job_abc123")
    assert final_job.status == JobStatus.READY
    assert final_job.result == {"overall": "OK"}


@pytest.mark.asyncio
async def test_evidence_and_findings_in_memory():
    """
    Evidence records and impact findings in InMemoryAdapter.
    """
    adapter = InMemoryAdapter()
    finding = ImpactFinding(
        findingId="find_1",
        changeReference="train.py:12",
        affectedArtifactId="sec_methodology",
        affectedArtifactType="SECTION",
        affectedTitle="Methodology",
        status=VerificationStatus.VERIFIED,
        risk="HIGH",
        reason="Verified learning rate propagation",
        evidenceIds=["ev_1"],
        evidencePath=["art_param", "art_code", "sec_methodology"],
        hasEvidence=True,
        analysisVersionId="v1_snapshot",
        createdAt="2026-09-14T12:00:00Z"
    )
    evidence = Evidence(
        evidenceId="ev_1",
        sourceArtifactId="art_param",
        targetArtifactId="sec_methodology",
        exactLocation="train.py:12",
        extractedValue="lr = 0.01",
        evidenceType=EvidenceType.DETERMINISTIC,
        relationshipType=RelationshipType.PARAMETER_REFERENCE,
        verification=VerificationStatus.VERIFIED,
        detail="Exact parameter reference in optimizer",
        analysisVersion="v1_snapshot",
        createdAt="2026-09-14T12:00:00Z"
    )

    await adapter.save_findings("v1_snapshot", [finding])
    await adapter.save_evidence("v1_snapshot", [evidence])

    loaded_findings = await adapter.get_findings_by_version("v1_snapshot")
    loaded_evidence = await adapter.get_evidence_by_version("v1_snapshot")

    assert len(loaded_findings) == 1
    assert loaded_findings[0].findingId == "find_1"
    assert loaded_findings[0].status == VerificationStatus.VERIFIED
    assert loaded_findings[0].hasEvidence is True

    assert len(loaded_evidence) == 1
    assert loaded_evidence[0].evidenceId == "ev_1"
    assert loaded_evidence[0].evidenceType == EvidenceType.DETERMINISTIC
