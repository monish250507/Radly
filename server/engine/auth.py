from fastapi import HTTPException, Depends, Header
from typing import Optional
from ..domain.auth_models import User, Role
from .persistence.db_adapter import get_db_provider, DatabaseProvider

# Mock JWT decode for local dev
async def get_current_user_or_guest(authorization: Optional[str] = Header(None)) -> Optional[User]:
    """
    If 'Bearer user_<id>' is passed, returns the User.
    Otherwise returns None (Guest).
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
        
    token = authorization.split(" ")[1]
    # In a real app, verify JWT signature here
    # Mock: token is just the email for testing
    email = token
    db = get_db_provider()
    user = await db.get_user_by_email(email)
    return user

async def get_current_user(user: Optional[User] = Depends(get_current_user_or_guest)) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

def require_role(min_role: Role):
    async def role_checker(
        project_id: str, 
        user: User = Depends(get_current_user)
    ):
        db = get_db_provider()
        membership = await db.get_project_membership(user.id, project_id)
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this project")
            
        role_hierarchy = {
            Role.OWNER: 5,
            Role.MAINTAINER: 4,
            Role.RESEARCHER: 3,
            Role.REVIEWER: 2,
            Role.VIEWER: 1
        }
        
        user_level = role_hierarchy.get(membership.role, 0)
        req_level = role_hierarchy.get(min_role, 0)
        
        if user_level < req_level:
            raise HTTPException(status_code=403, detail=f"Requires {min_role.value} privileges")
            
        return membership
    return role_checker
