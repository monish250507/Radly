from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

class Role(str, Enum):
    OWNER = 'OWNER'
    MAINTAINER = 'MAINTAINER'
    RESEARCHER = 'RESEARCHER'
    REVIEWER = 'REVIEWER'
    VIEWER = 'VIEWER'

class ConversationVisibility(str, Enum):
    PRIVATE = 'PRIVATE'
    PROJECT = 'PROJECT'
    RESEARCH_PR = 'RESEARCH_PR'

class PRStatus(str, Enum):
    OPEN = 'OPEN'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'

class InvitationStatus(str, Enum):
    PENDING = 'PENDING'
    ACCEPTED = 'ACCEPTED'
    REVOKED = 'REVOKED'
    EXPIRED = 'EXPIRED'

class User(BaseModel):
    id: str
    email: str
    created_at: str

class ProjectMembership(BaseModel):
    user_id: str
    project_id: str
    role: Role
    created_at: str

class Invitation(BaseModel):
    token: str
    project_id: str
    role: Role
    email: str
    status: InvitationStatus
    expires_at: str
    created_at: str

class Conversation(BaseModel):
    id: str
    project_id: str
    owner_id: Optional[str] = None # can be a User ID or a Guest Session ID
    visibility: ConversationVisibility = ConversationVisibility.PRIVATE
    title: str = "New Conversation"
    created_at: str

class ResearchPR(BaseModel):
    id: str
    project_id: str
    author_id: str
    base_version_id: str
    proposed_version_id: str
    status: PRStatus = PRStatus.OPEN
    created_at: str

class Comment(BaseModel):
    id: str
    pr_id: str
    author_id: str
    content: str
    created_at: str

class Review(BaseModel):
    id: str
    pr_id: str
    reviewer_id: str
    verdict: PRStatus
    content: str
    created_at: str

class AuditEvent(BaseModel):
    id: str
    project_id: str
    actor_id: str
    action: str # e.g. "invitation_sent", "member_added"
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
