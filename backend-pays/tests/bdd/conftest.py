"""
conftest.py — Fixtures partagées pour les tests BDD FutureKawa
Base SQLite en mémoire (pas de PostgreSQL requis dans le pipeline CI)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import get_db
from models import Base

# ── Base SQLite en mémoire ───────────────────────────────────
SQLALCHEMY_TEST_URL = "sqlite:///./futurekawa_bdd_test.db"

engine_test = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine_test
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Crée les tables une seule fois pour toute la session de tests."""
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture(scope="function")
def client():
    """
    Client HTTP FastAPI avec override de la dépendance DB.
    Réinitialise les tables à chaque test pour l'isolation.
    """
    from main import app

    app.dependency_overrides[get_db] = override_get_db

    Base.metadata.drop_all(bind=engine_test)
    Base.metadata.create_all(bind=engine_test)

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def db_session():
    """Session DB directe pour pré-peupler des données dans les steps Given."""
    Base.metadata.drop_all(bind=engine_test)
    Base.metadata.create_all(bind=engine_test)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Helpers pour créer les données prérequis ─────────────────

@pytest.fixture
def setup_config(client):
    """Crée une config par défaut et retourne sa réponse JSON."""
    resp = client.post("/config", json={
        "pays": "Bresil",
        "temp_ideale": 29.0,
        "hum_ideale": 55.0,
        "tolerance_temp": 3.0,
        "tolerance_hum": 2.0,
        "email_destinataire": "test@futurekawa.com",
        "intervalle_verification": 86400
    })
    return resp.json()


@pytest.fixture
def setup_exploitation(client, setup_config):
    """Crée une exploitation liée à la config et retourne sa réponse JSON."""
    resp = client.post("/exploitations", json={
        "nom": "Exploitation Test",
        "id_config": setup_config["id_config"]
    })
    return resp.json()


@pytest.fixture
def setup_entrepot(client, setup_exploitation):
    """Crée un entrepot lié à l'exploitation et retourne sa réponse JSON."""
    resp = client.post("/entrepots", json={
        "nom": "Entrepot Test",
        "localisation": "Sao Paulo",
        "id_exploitation": setup_exploitation["id_exploitation"]
    })
    return resp.json()


@pytest.fixture
def setup_capteur(client, setup_entrepot):
    """Crée un capteur lié à l'entrepôt et retourne sa réponse JSON."""
    resp = client.post("/capteurs", json={
        "type_capteur": "temperature_humidite",
        "reference": "CAP-001",
        "statut": "actif",
        "id_entrepot": setup_entrepot["id_entrepot"]
    })
    return resp.json()


@pytest.fixture
def setup_utilisateur(client):
    """Crée un utilisateur et retourne sa réponse JSON."""
    resp = client.post("/utilisateurs", json={
        "nom": "Dupont",
        "prenom": "Jean",
        "email": "jean.dupont@test.com",
        "mot_de_passe": "secret123",
        "actif": True
    })
    return resp.json()