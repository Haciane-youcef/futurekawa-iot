"""
FutureKawa — Tests d'Intégration (API REST)
tests/integration/test_api.py

Teste les endpoints FastAPI de bout en bout :
  - BDD SQLite de test (pas de PostgreSQL)
  - HTTP réel via TestClient
  - Dépendances FastAPI overridées (get_db)

Chaque classe nettoie ses données via fixture autouse pour
garantir l'isolation entre les tests.
"""

import os
import sys
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./futurekawa_integration_test.db"
os.environ["MQTT_BROKER"]  = "localhost"
os.environ["MQTT_PORT"]    = "1883"

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from database import get_db
from models import Base, Config, Lot, Alerte


# ─────────────────────────────────────────────────────────────
# Setup BDD de test
# ─────────────────────────────────────────────────────────────

engine_test = create_engine(
    "sqlite:///./futurekawa_integration_test.db",
    connect_args={"check_same_thread": False}
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine_test)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine_test)
    if os.path.exists("futurekawa_integration_test.db"):
        os.remove("futurekawa_integration_test.db")


# Helper pour ne pas répéter le payload config dans chaque test
CONFIG_BRESIL = {
    "pays": "Bresil",
    "temp_ideale": 29.0,
    "hum_ideale": 55.0,
    "tolerance_temp": 3.0,
    "tolerance_hum": 2.0,
    "email_destinataire": "resp@futurekawa.com",
    "intervalle_verification": 86400
}


# ════════════════════════════════════════════════════════════
# SANTÉ DE L'API
# ════════════════════════════════════════════════════════════

class TestSanteAPI:
    """Vérifie que l'API démarre et répond correctement."""

    def test_racine_repond_200(self, client):
        """GET / → 200."""
        assert client.get("/").status_code == 200

    def test_racine_retourne_champ_message(self, client):
        """GET / → body JSON avec clé 'message'."""
        data = client.get("/").json()
        assert "message" in data

    def test_racine_message_non_vide(self, client):
        """GET / → le message n'est pas une chaîne vide."""
        data = client.get("/").json()
        assert len(data["message"]) > 0

    def test_swagger_accessible(self, client):
        """GET /docs → 200 (Swagger UI)."""
        assert client.get("/docs").status_code == 200

    def test_openapi_json_accessible(self, client):
        """GET /openapi.json → 200 (schéma valide)."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        # Le schéma doit avoir les clés OpenAPI obligatoires
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema

    def test_route_inexistante_retourne_404(self, client):
        """GET /route-qui-nexiste-pas → 404."""
        assert client.get("/route-qui-nexiste-pas").status_code == 404


# ════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════

class TestConfiguration:
    """CRUD complet sur l'endpoint /config."""

    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Table Config vidée avant chaque test de cette classe."""
        db = TestingSession()
        db.query(Config).delete()
        db.commit()
        db.close()
        yield

    def test_creer_config(self, client):
        """POST /config → 200 avec les valeurs envoyées."""
        response = client.post("/config", json=CONFIG_BRESIL)
        assert response.status_code == 200
        data = response.json()
        assert data["pays"] == "Bresil"
        assert data["temp_ideale"] == 29.0
        assert data["hum_ideale"] == 55.0
        assert data["tolerance_temp"] == 3.0
        assert data["email_destinataire"] == "resp@futurekawa.com"

    def test_lire_config_existante(self, client):
        """GET /config après création → 200 avec les bonnes données."""
        client.post("/config", json=CONFIG_BRESIL)
        response = client.get("/config")
        assert response.status_code == 200
        assert response.json()["pays"] == "Bresil"

    def test_config_absente_retourne_404(self, client):
        """GET /config sans aucune config en base → 404."""
        assert client.get("/config").status_code == 404

    def test_double_creation_retourne_400(self, client):
        """POST /config deux fois → 400 (une seule config autorisée)."""
        client.post("/config", json=CONFIG_BRESIL)
        response = client.post("/config", json=CONFIG_BRESIL)
        assert response.status_code == 400

    def test_modifier_config_email(self, client):
        """PUT /config avec nouvel email → 200."""
        client.post("/config", json=CONFIG_BRESIL)
        response = client.put("/config", json={"email_destinataire": "new@test.com"})
        assert response.status_code == 200

    def test_modifier_config_email_persiste(self, client):
        """PUT /config → GET /config retourne la nouvelle valeur."""
        client.post("/config", json=CONFIG_BRESIL)
        client.put("/config", json={"email_destinataire": "updated@test.com"})
        data = client.get("/config").json()
        assert data["email_destinataire"] == "updated@test.com"

    def test_modifier_config_absente_retourne_404(self, client):
        """PUT /config sans config en base → 404."""
        response = client.put("/config", json={"email_destinataire": "x@x.com"})
        assert response.status_code == 404


# ════════════════════════════════════════════════════════════
# LOTS
# ════════════════════════════════════════════════════════════

class TestLots:
    """CRUD complet sur l'endpoint /lots."""

    LOT_PAYLOAD = {
        "lot_id": "LOT-INT-001",
        "pays": "Bresil",
        "exploitation": "Exploitation Alto Paraíso",
        "entrepot": "Entrepot Goiás"
    }

    @pytest.fixture(autouse=True)
    def cleanup_lots(self):
        """Lots de test supprimés avant chaque test."""
        db = TestingSession()
        db.query(Lot).filter(Lot.lot_id.like("LOT-INT-%")).delete(synchronize_session=False)
        db.commit()
        db.close()
        yield

    def test_creer_lot_valide(self, client):
        """POST /lots → 200 avec lot_id et statut 'conforme'."""
        response = client.post("/lots", json=self.LOT_PAYLOAD)
        assert response.status_code == 201
        data = response.json()
        assert data["lot_id"] == "LOT-INT-001"
        assert data["statut"] == "conforme"

    def test_lot_cree_contient_date_stockage(self, client):
        """Un lot nouvellement créé doit avoir un champ date_stockage."""
        response = client.post("/lots", json=self.LOT_PAYLOAD)
        assert "date_stockage" in response.json()
        assert response.json()["date_stockage"] is not None

    def test_liste_lots_retourne_liste(self, client):
        """GET /lots → toujours une liste (même vide)."""
        response = client.get("/lots")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_lot_cree_apparait_dans_liste(self, client):
        """Un lot créé est visible dans GET /lots."""
        client.post("/lots", json=self.LOT_PAYLOAD)
        lot_ids = [l["lot_id"] for l in client.get("/lots").json()]
        assert "LOT-INT-001" in lot_ids

    def test_lire_lot_par_id(self, client):
        """GET /lots/{id} → 200 avec le bon lot."""
        client.post("/lots", json=self.LOT_PAYLOAD)
        response = client.get("/lots/LOT-INT-001")
        assert response.status_code == 200
        assert response.json()["lot_id"] == "LOT-INT-001"

    def test_lot_inexistant_retourne_404(self, client):
        """GET /lots/ID-INCONNU → 404."""
        assert client.get("/lots/LOT-INEXISTANT-99999").status_code == 404

    def test_lot_id_doublon_retourne_erreur(self, client):
        """POST /lots deux fois avec le même lot_id → 4xx ou 500."""
        client.post("/lots", json=self.LOT_PAYLOAD)
        response = client.post("/lots", json=self.LOT_PAYLOAD)
        assert response.status_code in [400, 422, 500]

    def test_modifier_statut_en_alerte(self, client):
        """PUT /lots/{id}/statut?statut=en_alerte → 200 avec nouveau statut."""
        client.post("/lots", json=self.LOT_PAYLOAD)
        response = client.put("/lots/LOT-INT-001/statut", params={"statut": "en_alerte"})
        assert response.status_code == 200
        assert response.json()["statut"] == "en_alerte"

    def test_modifier_statut_perime(self, client):
        """PUT /lots/{id}/statut?statut=perime → statut correctement mis à jour."""
        client.post("/lots", json=self.LOT_PAYLOAD)
        response = client.put("/lots/LOT-INT-001/statut", params={"statut": "perime"})
        assert response.status_code == 200
        assert response.json()["statut"] == "perime"

    def test_modifier_statut_lot_inexistant_404(self, client):
        """PUT /lots/INCONNU/statut → 404."""
        response = client.put("/lots/LOT-INEXISTANT/statut", params={"statut": "perime"})
        assert response.status_code == 404

    def test_lots_tries_fifo(self, client):
        """GET /lots → les lots sont triés du plus ancien au plus récent."""
        client.post("/lots", json={
            "lot_id": "LOT-INT-FIFO-A", "pays": "Bresil",
            "exploitation": "Expl A", "entrepot": "Ent A"
        })
        client.post("/lots", json={
            "lot_id": "LOT-INT-FIFO-B", "pays": "Bresil",
            "exploitation": "Expl B", "entrepot": "Ent B"
        })
        lots = client.get("/lots").json()
        dates = [l["date_stockage"] for l in lots if l["lot_id"].startswith("LOT-INT-FIFO")]
        assert dates == sorted(dates)

    def test_creer_lot_champs_retournes(self, client):
        """POST /lots → la réponse contient tous les champs attendus."""
        response = client.post("/lots", json=self.LOT_PAYLOAD)
        data = response.json()
        for champ in ["lot_id", "pays", "exploitation", "entrepot", "statut", "date_stockage"]:
            assert champ in data, f"Champ manquant dans la réponse : {champ}"


# ════════════════════════════════════════════════════════════
# MESURES IoT
# ════════════════════════════════════════════════════════════

class TestMesures:
    """Endpoints de lecture des mesures IoT."""

    def test_liste_mesures_retourne_liste(self, client):
        """GET /mesures → toujours une liste."""
        response = client.get("/mesures")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_dernieres_mesures_limite_respectee(self, client):
        """GET /mesures/dernieres/5 → au maximum 5 éléments."""
        response = client.get("/mesures/dernieres/5")
        assert response.status_code == 200
        assert len(response.json()) <= 5

    def test_dernieres_mesures_limite_1(self, client):
        """GET /mesures/dernieres/1 → au maximum 1 élément."""
        response = client.get("/mesures/dernieres/1")
        assert response.status_code == 200
        assert len(response.json()) <= 1


# ════════════════════════════════════════════════════════════
# ALERTES
# ════════════════════════════════════════════════════════════

class TestAlertes:
    """Endpoints CRUD des alertes."""

    @pytest.fixture(autouse=True)
    def cleanup_alertes(self):
        """Table Alerte vidée avant chaque test."""
        db = TestingSession()
        db.query(Alerte).delete()
        db.commit()
        db.close()
        yield

    def test_liste_alertes_retourne_liste(self, client):
        """GET /alertes → toujours une liste."""
        response = client.get("/alertes")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_count_retourne_total_et_non_lues(self, client):
        """GET /alertes/count → JSON avec 'total' et 'non_lues'."""
        response = client.get("/alertes/count")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "non_lues" in data

    def test_count_valeurs_numeriques(self, client):
        """GET /alertes/count → 'total' et 'non_lues' sont des entiers >= 0."""
        data = client.get("/alertes/count").json()
        assert isinstance(data["total"], int)
        assert isinstance(data["non_lues"], int)
        assert data["total"] >= 0
        assert data["non_lues"] >= 0

    def test_non_lues_retourne_liste(self, client):
        """GET /alertes/non-lues → toujours une liste."""
        response = client.get("/alertes/non-lues")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_supprimer_alerte_inexistante_404(self, client):
        """DELETE /alertes/999999 → 404."""
        assert client.delete("/alertes/999999").status_code == 404

    def test_marquer_alerte_inexistante_lue_404(self, client):
        """PUT /alertes/999999/lue → 404."""
        assert client.put("/alertes/999999/lue").status_code == 404

    def test_supprimer_toutes_alertes(self, client):
        """DELETE /alertes → 200 (même si la table est déjà vide)."""
        assert client.delete("/alertes").status_code == 200

    def test_marquer_toutes_lues_retourne_message(self, client):
        """PUT /alertes/toutes/lues → 200 avec champ 'message'."""
        response = client.put("/alertes/toutes/lues")
        assert response.status_code == 200
        assert "message" in response.json()

    def test_count_vide_apres_suppression(self, client):
        """Après DELETE /alertes, le count total doit être 0."""
        client.delete("/alertes")
        data = client.get("/alertes/count").json()
        assert data["total"] == 0

    def test_non_lues_vide_apres_marquer_toutes_lues(self, client):
        """Après PUT /alertes/toutes/lues, le count non_lues doit être 0."""
        client.put("/alertes/toutes/lues")
        data = client.get("/alertes/count").json()
        assert data["non_lues"] == 0
