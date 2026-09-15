import logging
import os
from typing import Any
import jwt
from fastapi import Depends, Header, HTTPException

from ..domain.auth_models import Role, User
from .persistence.db_adapter import get_db_provider

JWT_SECRET = os.getenv("JWT_SECRET", "dev_secret_do_not_use_in_prod_key_32b")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ISSUER = os.getenv("JWT_ISSUER", "paperblast_auth")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "paperblast")

logger = logging.getLogger("paperblast.auth")


def create_access_token(payload: dict[str, Any], secret: str = JWT_SECRET) -> str:
    """Create a signed JWT token with standard issuer and audience."""
    data = payload.copy()
    data.setdefault("iss", JWT_ISSUER)
    data.setdefault("aud", JWT_AUDIENCE)
    return jwt.encode(data, secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str, secret: str = JWT_SECRET, issuer: str = JWT_ISSUER, audience: str = JWT_AUDIENCE) -> dict[str, Any]:
    """
    Validate and decode a JWT token against secret, algorithm, issuer, and audience.
    Raises specific jwt exceptions on validation failure (P1-4).
    """
    return jwt.decode(
        token,
        secret,
        algorithms=[JWT_ALGORITHM],
        issuer=issuer,
        audience=audience
    )


async def get_current_user_or_guest(authorization: str | None = Header(None)) -> User | None:
    """
    Validates JWT token from Authorization header.
    If valid and user exists, returns the User.
    Otherwise returns None (Guest).
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
        
    token = authorization.split(" ")[1]
    
    try:
        payload = decode_token(token)
        email = payload.get("email")
        if not email:
            return None
    except jwt.ExpiredSignatureError:
        logger.warning("JWT validation failed: Token has expired")
        return None
    except jwt.InvalidIssuerError:
        logger.warning("JWT validation failed: Invalid issuer")
        return None
    except jwt.InvalidAudienceError:
        logger.warning("JWT validation failed: Invalid audience")
        return None
    except jwt.InvalidSignatureError:
        logger.warning("JWT validation failed: Invalid signature")
        return None
    except jwt.PyJWTError as e:
        logger.warning(f"JWT validation failed: {str(e)}")
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
