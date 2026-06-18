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


# ════════════════════════════════════════════════════════════
# CONFIG — Données de test réutilisables
# ════════════════════════════════════════════════════════════

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


# ════════════════════════════════════════════════════════════
# CHAÎNE DE PRÉREQUIS : Config → Exploitation → Entrepot
# → Capteur → Utilisateur
# (chaque fixture appelle l'API et retourne le JSON créé)
# ════════════════════════════════════════════════════════════

@pytest.fixture
def config_bresil(client):
    """Crée la config Brésil en BDD et retourne son JSON."""
    resp = client.post("/config", json={
        "pays"                   : "Bresil",
        "temp_ideale"            : 29.0,
        "hum_ideale"             : 55.0,
        "tolerance_temp"         : 3.0,
        "tolerance_hum"          : 2.0,
        "email_destinataire"     : "resp@futurekawa.com",
        "intervalle_verification": 86400
    })
    return resp.json()


@pytest.fixture
def exploitation_bresil(client, config_bresil):
    """Crée une exploitation liée à la config et retourne son JSON."""
    resp = client.post("/exploitations", json={
        "nom"      : "Exploitation Alto Paraíso",
        "id_config": config_bresil["id_config"]
    })
    return resp.json()


@pytest.fixture
def entrepot_bresil(client, exploitation_bresil):
    """Crée un entrepôt lié à l'exploitation et retourne son JSON."""
    resp = client.post("/entrepots", json={
        "nom"            : "Entrepot Goiás",
        "localisation"   : "Goiás, Brésil",
        "id_exploitation": exploitation_bresil["id_exploitation"]
    })
    return resp.json()


@pytest.fixture
def capteur_bresil(client, entrepot_bresil):
    """Crée un capteur lié à l'entrepôt et retourne son JSON."""
    resp = client.post("/capteurs", json={
        "type_capteur": "temperature_humidite",
        "reference"   : "CAP-TEST-001",
        "statut"      : "actif",
        "id_entrepot" : entrepot_bresil["id_entrepot"]
    })
    return resp.json()


@pytest.fixture
def utilisateur_test(client):
    """Crée un utilisateur de test et retourne son JSON."""
    resp = client.post("/utilisateurs", json={
        "nom"         : "Dupont",
        "prenom"      : "Jean",
        "email"       : "jean.dupont@test.com",
        "mot_de_passe": "secret123",
        "actif"       : True
    })
    return resp.json()


@pytest.fixture
def utilisateur_ethiopie(client):
    """Crée un second utilisateur (Éthiopie) et retourne son JSON."""
    resp = client.post("/utilisateurs", json={
        "nom"         : "Tadesse",
        "prenom"      : "Abebe",
        "email"       : "abebe@test.com",
        "mot_de_passe": "secret456",
        "actif"       : True
    })
    return resp.json()


# ════════════════════════════════════════════════════════════
# LOTS — Données complètes (FK résolues via fixtures ci-dessus)
# ════════════════════════════════════════════════════════════

@pytest.fixture
def lot_bresil_data(entrepot_bresil, utilisateur_test):
    """Payload complet pour créer un lot Brésil."""
    return {
        "id_lot"         : "LOT-BR-TEST-001",
        "id_entrepot"    : entrepot_bresil["id_entrepot"],
        "id_utilisateur" : utilisateur_test["id_utilisateur"]
    }


@pytest.fixture
def lot_ethiopia_data(entrepot_bresil, utilisateur_ethiopie):
    """Payload complet pour créer un lot Éthiopie (réutilise l'entrepôt)."""
    return {
        "id_lot"         : "LOT-ET-TEST-001",
        "id_entrepot"    : entrepot_bresil["id_entrepot"],
        "id_utilisateur" : utilisateur_ethiopie["id_utilisateur"]
    }


# ════════════════════════════════════════════════════════════
# MESURE — Payload réutilisable
# ════════════════════════════════════════════════════════════

@pytest.fixture
def mesure_normale_data(capteur_bresil):
    """Payload pour une mesure dans les seuils normaux."""
    return {
        "temperature": 29.0,
        "humidite"   : 55.0,
        "id_capteur" : capteur_bresil["id_capteur"]
    }


@pytest.fixture
def mesure_hors_seuils_data(capteur_bresil):
    """Payload pour une mesure hors seuils (déclenche alertes)."""
    return {
        "temperature": 40.0,
        "humidite"   : 80.0,
        "id_capteur" : capteur_bresil["id_capteur"]
    }