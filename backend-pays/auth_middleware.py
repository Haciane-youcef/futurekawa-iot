import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt


JWT_SECRET = os.getenv("JWT_SECRET", "futurekawa-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """Validate the JWT emitted by backend-central and return its payload."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token manquant",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expire",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[dict]:
    """Return a JWT payload when auth is enabled or a token is supplied."""
    auth_required = os.getenv("AUTH_REQUIRED", "true").lower() in ("1", "true", "yes", "on")
    if not auth_required and not credentials:
        return None
    return get_current_user(credentials)


def require_role(*roles: str):
    """Dependency requiring at least one role from the JWT."""
    def _check(current_user: dict = Depends(get_current_user)):
        if not any(role in current_user.get("roles", []) for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role requis : {list(roles)}",
            )
        return current_user

    return _check


def get_user_entrepots(current_user: dict) -> list[int]:
    """Return all warehouses accessible through the JWT payload."""
    entrepots = []
    for access in current_user.get("accesses", []):
        entrepots.extend(access.get("entrepots", []))
    return entrepots


def can_access_entrepot(entrepot_id: int, current_user: dict) -> bool:
    """Admins can access all warehouses; other users are scoped by JWT access."""
    if "admin" in current_user.get("roles", []):
        return True
    return entrepot_id in get_user_entrepots(current_user)
