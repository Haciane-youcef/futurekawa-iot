"""
FutureKawa — conftest.py (racine)
Configuration pytest partagée : fixtures de base, override DB SQLite.
Chargé automatiquement par pytest avant tous les tests.
"""

import os
import sys
import pytest

# ── Variables d'env AVANT tout import de l'app ──────────────
os.environ.setdefault("DATABASE_URL", "sqlite:///./futurekawa_test.db")
os.environ.setdefault("MQTT_BROKER",  "localhost")
os.environ.setdefault("MQTT_PORT",    "1883")

# ── Path Python ──────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app
from database import get_db
from models import Base

# ── Moteur SQLite test (partagé entre tous les tests) ────────
TEST_DB_URL = "sqlite:///./futurekawa_test.db"

engine_test = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine_test
)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Override de la dépendance FastAPI
app.dependency_overrides[get_db] = override_get_db


# ════════════════════════════════════════════════════════════
# FIXTURES PARTAGÉES (disponibles dans tous les fichiers test)
# ════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def client():
    """Client de test FastAPI — session complète."""
    Base.metadata.create_all(bind=engine_test)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture(autouse=False)
def clean_db():
    """Remet les tables à zéro avant chaque test qui le demande."""
    Base.metadata.drop_all(bind=engine_test)
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)
    Base.metadata.create_all(bind=engine_test)


# ── Données de test réutilisables ────────────────────────────

@pytest.fixture
def lot_bresil_data():
    return {
        "lot_id"      : "LOT-BR-TEST-001",
        "pays"        : "Bresil",
        "exploitation": "Exploitation Alto Paraíso",
        "entrepot"    : "Entrepot Goiás"
    }

@pytest.fixture
def lot_ethiopia_data():
    return {
        "lot_id"      : "LOT-ET-TEST-001",
        "pays"        : "Ethiopie",
        "exploitation": "Exploitation Yirgacheffe",
        "entrepot"    : "Entrepot Addis"
    }

@pytest.fixture
def config_bresil_data():
    return {
        "pays"                   : "Bresil",
        "temp_ideale"            : 29.0,
        "hum_ideale"             : 55.0,
        "tolerance_temp"         : 3.0,
        "tolerance_hum"          : 2.0,
        "email_destinataire"     : "resp@futurekawa.com",
        "intervalle_verification": 86400
    }

@pytest.fixture
def config_hors_seuils():
    """Config avec seuils très serrés pour déclencher des alertes."""
    return {
        "pays"                   : "Test",
        "temp_ideale"            : 25.0,
        "hum_ideale"             : 50.0,
        "tolerance_temp"         : 0.1,
        "tolerance_hum"          : 0.1,
        "email_destinataire"     : "test@futurekawa.com",
        "intervalle_verification": 60
    }
