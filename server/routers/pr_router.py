from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from datetime import datetime
import uuid

from ..engine.auth import require_role, get_current_user
from ..engine.persistence.db_adapter import get_db_provider
from ..domain.auth_models import User, Role, ResearchPR, Comment, Review, PRStatus

pr_router = APIRouter(prefix="/api/prs", tags=["Research PR"])

@pr_router.post("")
async def create_research_pr(
    project_id: str,
    base_version_id: str,
    proposed_version_id: str,
    user: User = Depends(get_current_user)
):
    # Enforce RESEARCHER or above to create a PR
    checker = require_role(Role.RESEARCHER)
    await checker(project_id, user)
    
    db = get_db_provider()
    pr = ResearchPR(
        id=f"pr_{uuid.uuid4().hex[:8]}",
        project_id=project_id,
        author_id=user.id,
        base_version_id=base_version_id,
        proposed_version_id=proposed_version_id,
        status=PRStatus.OPEN,
        created_at=datetime.utcnow().isoformat() + "Z"
    )
    
    # Store it in db (mocked via hasattr)
    if hasattr(db, 'prs'):
        db.prs[pr.id] = pr
    else:
        db.prs = {pr.id: pr}
        
    return {"status": "success", "pr": pr}

@pr_router.post("/{pr_id}/comments")
async def add_comment(
    pr_id: str,
    content: str,
    user: User = Depends(get_current_user)
):
    db = get_db_provider()
    if not hasattr(db, 'prs') or pr_id not in db.prs:
        raise HTTPException(status_code=404, detail="PR not found")
        
    pr = db.prs[pr_id]
    
    # Enforce VIEWER or above to comment
    checker = require_role(Role.VIEWER)
    await checker(pr.project_id, user)
    
    comment = Comment(
        id=f"comment_{uuid.uuid4().hex[:8]}",
        pr_id=pr_id,
        author_id=user.id,
        content=content,
        created_at=datetime.utcnow().isoformat() + "Z"
    )
    
    if hasattr(db, 'comments'):
        db.comments.append(comment)
    else:
        db.comments = [comment]
        
    return {"status": "success", "comment": comment}

@pr_router.post("/{pr_id}/review")
async def submit_review(
    pr_id: str,
    verdict: PRStatus,
    content: str,
    user: User = Depends(get_current_user)
):
    db = get_db_provider()
    if not hasattr(db, 'prs') or pr_id not in db.prs:
        raise HTTPException(status_code=404, detail="PR not found")
        
    pr = db.prs[pr_id]
    
    # Enforce REVIEWER or above to review
    checker = require_role(Role.REVIEWER)
    await checker(pr.project_id, user)
    
    review = Review(
        id=f"rev_{uuid.uuid4().hex[:8]}",
        pr_id=pr_id,
        reviewer_id=user.id,
        verdict=verdict,
        content=content,
        created_at=datetime.utcnow().isoformat() + "Z"
    )
    
    if hasattr(db, 'reviews'):
        db.reviews.append(review)
    else:
        db.reviews = [review]
        
    pr.status = verdict # update PR state
        
    return {"status": "success", "review": review, "pr_status": pr.status}
