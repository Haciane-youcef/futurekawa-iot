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
    # Import ici pour éviter les effets de bord à l'import
    from main import app

    app.dependency_overrides[get_db] = override_get_db

    # Réinitialisation des données entre chaque scénario
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
