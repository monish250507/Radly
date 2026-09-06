import os
import jwt
from fastapi import Depends, Header, HTTPException

from ..domain.auth_models import Role, User
from .persistence.db_adapter import get_db_provider

JWT_SECRET = os.getenv("JWT_SECRET", "dev_secret_do_not_use_in_prod")
JWT_ALGORITHM = "HS256"

async def get_current_user_or_guest(authorization: str | None = Header(None)) -> User | None:
    """
    Validates JWT token. If valid, returns the User.
    Otherwise returns None (Guest).
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
        
    token = authorization.split(" ")[1]
    
    try:
        # P1 FIX: Validate signature, issuer, and audience
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], audience="paperblast", issuer="paperblast_auth")
        email = payload.get("email")
        if not email:
            return None
    except jwt.PyJWTError as e:
        import logging
        logging.warning(f"JWT Validation failed: {str(e)}")
        return None

    db = get_db_provider()
    user = await db.get_user_by_email(email)
    return user

async def get_current_user(user: User | None = Depends(get_current_user_or_guest)) -> User:
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
