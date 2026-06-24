import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

# Clé partagée avec backend-central — doit être identique via variable d'env
JWT_SECRET    = os.getenv("JWT_SECRET", "futurekawa-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() == "true"

bearer_scheme = HTTPBearer(auto_error=False)


# ─────────────────────────────────────────────────────────────
# Auth obligatoire (routes protégées)
# ─────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────
# Auth optionnelle (routes mixtes : publiques + authentifiées)
# ─────────────────────────────────────────────────────────────

def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[dict]:
    """Retourne le payload JWT si présent et valide, sinon None.
    Ne lève jamais d'exception — idéal pour les routes optionnellement protégées."""
    if not credentials:
        return None
    try:
        return jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


# ─────────────────────────────────────────────────────────────
# Contrôle de rôles
# ─────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────
# Accès entrepôts
# ─────────────────────────────────────────────────────────────

def get_user_entrepots(current_user: dict) -> list:
    """Retourne la liste des entrepôts accessibles à l'utilisateur selon son JWT."""
    entrepots = []
    for access in current_user.get("accesses", []):
        entrepots.extend(access.get("entrepots", []))
    return entrepots


def can_access_entrepot(entrepot_id: int, current_user: dict) -> bool:
    """En mode test (AUTH_REQUIRED=false), tout est autorisé.
    Admin voit tout. Sinon vérifie que l'entrepôt est dans les accès du JWT."""
    if not AUTH_REQUIRED:
        return True
    if "admin" in current_user.get("roles", []):
        return True
    return entrepot_id in get_user_entrepots(current_user)