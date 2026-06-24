import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

# Clé partagée avec backend-central — doit être identique via variable d'env
JWT_SECRET    = os.getenv("JWT_SECRET", "futurekawa-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """Valide le JWT émis par backend-central et retourne le payload."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token manquant",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(*roles: str):
    """Dépendance : l'utilisateur doit posséder au moins un des rôles listés."""
    def _check(current_user: dict = Depends(get_current_user)):
        if not any(r in current_user.get("roles", []) for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle requis : {list(roles)}",
            )
        return current_user
    return _check


def get_user_entrepots(current_user: dict) -> list[int]:
    """Retourne la liste des entrepôts accessibles à l'utilisateur selon son JWT."""
    entrepots = []
    for access in current_user.get("accesses", []):
        entrepots.extend(access.get("entrepots", []))
    return entrepots


def can_access_entrepot(entrepot_id: int, current_user: dict) -> bool:
    """Admin voit tout. Sinon vérifie que l'entrepôt est dans les accès du JWT."""
    if "admin" in current_user.get("roles", []):
        return True
    return entrepot_id in get_user_entrepots(current_user)
