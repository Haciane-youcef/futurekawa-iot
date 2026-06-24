from unittest.mock import patch
from jose import jwt

from auth_middleware import JWT_ALGORITHM, JWT_SECRET, can_access_entrepot, get_user_entrepots


def test_jwt_payload_decode_compatible_backend_central():
    payload = {
        "sub": "42",
        "roles": ["responsable_entrepot"],
        "accesses": [{"entrepots": [1, 2]}],
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    assert decoded["sub"] == "42"
    assert decoded["roles"] == ["responsable_entrepot"]


def test_can_access_entrepot_depuis_accesses_jwt():
    current_user = {
        "roles": ["responsable_entrepot"],
        "accesses": [{"entrepots": [3, 4]}],
    }

    with patch("auth_middleware.AUTH_REQUIRED", True):
        assert get_user_entrepots(current_user) == [3, 4]
        assert can_access_entrepot(3, current_user) is True
        assert can_access_entrepot(9, current_user) is False


def test_admin_can_access_all_entrepots():
    with patch("auth_middleware.AUTH_REQUIRED", True):
        assert can_access_entrepot(999, {"roles": ["admin"], "accesses": []}) is True