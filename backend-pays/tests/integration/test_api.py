"""
FutureKawa — Tests d'Intégration (API REST)
tests/integration/test_api.py
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
from models import (
    Base, Config, Exploitation, Entrepot, Capteur, Mesure, Lot,
    AlerteMesure, AlerteLot, Utilisateur
)

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


# Helpers
CONFIG_BRESIL = {
    "pays": "Bresil",
    "temp_ideale": 29.0,
    "hum_ideale": 55.0,
    "tolerance_temp": 3.0,
    "tolerance_hum": 2.0,
    "email_destinataire": "resp@futurekawa.com",
    "intervalle_verification": 86400
}


def _creer_chain_complete(client):
    """Crée config → exploitation → entrepot → capteur → utilisateur et retourne les ids."""
    cfg = client.post("/config", json=CONFIG_BRESIL).json()
    expl = client.post("/exploitations", json={
        "nom": "Exploitation Alto Paraiso",
        "id_config": cfg["id_config"]
    }).json()
    ent = client.post("/entrepots", json={
        "nom": "Entrepot Goias",
        "localisation": "Goias, Bresil",
        "id_exploitation": expl["id_exploitation"]
    }).json()
    cap = client.post("/capteurs", json={
        "type_capteur": "temperature_humidite",
        "reference": "CAP-INT-001",
        "id_entrepot": ent["id_entrepot"]
    }).json()
    usr = client.post("/utilisateurs", json={
        "nom": "Silva",
        "prenom": "Maria",
        "email": "maria@test.com",
        "mot_de_passe": "pwd123"
    }).json()
    return {
        "config": cfg,
        "exploitation": expl,
        "entrepot": ent,
        "capteur": cap,
        "utilisateur": usr
    }


# ════════════════════════════════════════════════════════════
# SANTÉ DE L'API
# ════════════════════════════════════════════════════════════

class TestSanteAPI:

    def test_racine_repond_200(self, client):
        assert client.get("/").status_code == 200

    def test_racine_retourne_champ_message(self, client):
        data = client.get("/").json()
        assert "message" in data

    def test_racine_message_non_vide(self, client):
        data = client.get("/").json()
        assert len(data["message"]) > 0

    def test_swagger_accessible(self, client):
        assert client.get("/docs").status_code == 200

    def test_openapi_json_accessible(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema

    def test_route_inexistante_retourne_404(self, client):
        assert client.get("/route-qui-nexiste-pas").status_code == 404


# ════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════

class TestConfiguration:

    @pytest.fixture(autouse=True)
    def reset_config(self):
        db = TestingSession()
        db.query(Config).delete()
        db.commit()
        db.close()
        yield

    def test_creer_config(self, client):
        response = client.post("/config", json=CONFIG_BRESIL)
        assert response.status_code == 200
        data = response.json()
        assert data["pays"] == "Bresil"
        assert data["temp_ideale"] == 29.0
        assert data["hum_ideale"] == 55.0
        assert data["tolerance_temp"] == 3.0
        assert data["email_destinataire"] == "resp@futurekawa.com"

    def test_lire_config_existante(self, client):
        client.post("/config", json=CONFIG_BRESIL)
        response = client.get("/config")
        assert response.status_code == 200
        assert response.json()["pays"] == "Bresil"

    def test_config_absente_retourne_404(self, client):
        assert client.get("/config").status_code == 404

    def test_double_creation_retourne_400(self, client):
        client.post("/config", json=CONFIG_BRESIL)
        response = client.post("/config", json=CONFIG_BRESIL)
        assert response.status_code == 400

    def test_modifier_config_email(self, client):
        client.post("/config", json=CONFIG_BRESIL)
        response = client.put("/config", json={"email_destinataire": "new@test.com"})
        assert response.status_code == 200

    def test_modifier_config_email_persiste(self, client):
        client.post("/config", json=CONFIG_BRESIL)
        client.put("/config", json={"email_destinataire": "updated@test.com"})
        data = client.get("/config").json()
        assert data["email_destinataire"] == "updated@test.com"

    def test_modifier_config_absente_retourne_404(self, client):
        response = client.put("/config", json={"email_destinataire": "x@x.com"})
        assert response.status_code == 404


# ════════════════════════════════════════════════════════════
# EXPLOITATIONS
# ════════════════════════════════════════════════════════════

class TestExploitations:

    @pytest.fixture(autouse=True)
    def cleanup(self):
        db = TestingSession()
        db.query(Exploitation).delete()
        db.query(Config).delete()
        db.commit()
        db.close()
        yield

    def test_creer_exploitation(self, client):
        cfg = client.post("/config", json=CONFIG_BRESIL).json()
        response = client.post("/exploitations", json={
            "nom": "Fazenda Boa Vista",
            "id_config": cfg["id_config"]
        })
        assert response.status_code == 201
        assert response.json()["nom"] == "Fazenda Boa Vista"

    def test_liste_exploitations(self, client):
        response = client.get("/exploitations")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_config_inexistante_retourne_404(self, client):
        response = client.post("/exploitations", json={
            "nom": "Test", "id_config": 9999
        })
        assert response.status_code == 404


# ════════════════════════════════════════════════════════════
# ENTREPOTS
# ════════════════════════════════════════════════════════════

class TestEntrepots:

    @pytest.fixture(autouse=True)
    def cleanup(self):
        db = TestingSession()
        db.query(Entrepot).delete()
        db.query(Exploitation).delete()
        db.query(Config).delete()
        db.commit()
        db.close()
        yield

    def test_creer_entrepot(self, client):
        chain = _creer_chain_complete(client)
        response = client.post("/entrepots", json={
            "nom": "Entrepot 2",
            "localisation": "Rio de Janeiro",
            "id_exploitation": chain["exploitation"]["id_exploitation"]
        })
        assert response.status_code == 201

    def test_liste_entrepots(self, client):
        response = client.get("/entrepots")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ════════════════════════════════════════════════════════════
# CAPTEURS
# ════════════════════════════════════════════════════════════

class TestCapteurs:

    @pytest.fixture(autouse=True)
    def cleanup(self):
        db = TestingSession()
        db.query(Capteur).delete()
        db.query(Entrepot).delete()
        db.query(Exploitation).delete()
        db.query(Config).delete()
        db.commit()
        db.close()
        yield

    def test_creer_capteur(self, client):
        chain = _creer_chain_complete(client)
        response = client.post("/capteurs", json={
            "type_capteur": "temperature",
            "reference": "CAP-NEW-001",
            "id_entrepot": chain["entrepot"]["id_entrepot"]
        })
        assert response.status_code == 201
        assert response.json()["statut"] == "actif"

    def test_liste_capteurs(self, client):
        response = client.get("/capteurs")
        assert response.status_code == 200


# ════════════════════════════════════════════════════════════
# LOTS
# ════════════════════════════════════════════════════════════

class TestLots:

    @pytest.fixture(autouse=True)
    def cleanup_lots(self):
        db = TestingSession()
        db.query(Lot).filter(Lot.id_lot.like("LOT-INT-%")).delete(synchronize_session=False)
        db.commit()
        db.close()
        yield

    def test_creer_lot_valide(self, client):
        chain = _creer_chain_complete(client)
        response = client.post("/lots", json={
            "id_lot": "LOT-INT-001",
            "id_entrepot": chain["entrepot"]["id_entrepot"],
            "id_utilisateur": chain["utilisateur"]["id_utilisateur"]
        })
        assert response.status_code == 201
        data = response.json()
        assert data["id_lot"] == "LOT-INT-001"
        assert data["statut"] == "conforme"

    def test_lot_cree_contient_date_stockage(self, client):
        chain = _creer_chain_complete(client)
        response = client.post("/lots", json={
            "id_lot": "LOT-INT-DATE",
            "id_entrepot": chain["entrepot"]["id_entrepot"],
            "id_utilisateur": chain["utilisateur"]["id_utilisateur"]
        })
        assert "date_stockage" in response.json()
        assert response.json()["date_stockage"] is not None

    def test_liste_lots_retourne_liste(self, client):
        response = client.get("/lots")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_lot_cree_apparait_dans_liste(self, client):
        chain = _creer_chain_complete(client)
        client.post("/lots", json={
            "id_lot": "LOT-INT-VISIBLE",
            "id_entrepot": chain["entrepot"]["id_entrepot"],
            "id_utilisateur": chain["utilisateur"]["id_utilisateur"]
        })
        lot_ids = [l["id_lot"] for l in client.get("/lots").json()]
        assert "LOT-INT-VISIBLE" in lot_ids

    def test_lire_lot_par_id(self, client):
        chain = _creer_chain_complete(client)
        client.post("/lots", json={
            "id_lot": "LOT-INT-READ",
            "id_entrepot": chain["entrepot"]["id_entrepot"],
            "id_utilisateur": chain["utilisateur"]["id_utilisateur"]
        })
        response = client.get("/lots/LOT-INT-READ")
        assert response.status_code == 200
        assert response.json()["id_lot"] == "LOT-INT-READ"

    def test_lot_inexistant_retourne_404(self, client):
        assert client.get("/lots/LOT-INEXISTANT-99999").status_code == 404

    def test_lot_id_doublon_retourne_erreur(self, client):
        chain = _creer_chain_complete(client)
        payload = {
            "id_lot": "LOT-INT-DUPL",
            "id_entrepot": chain["entrepot"]["id_entrepot"],
            "id_utilisateur": chain["utilisateur"]["id_utilisateur"]
        }
        client.post("/lots", json=payload)
        response = client.post("/lots", json=payload)
        assert response.status_code in [400, 409, 422, 500]

    def test_modifier_statut_en_alerte(self, client):
        chain = _creer_chain_complete(client)
        client.post("/lots", json={
            "id_lot": "LOT-INT-STATUT",
            "id_entrepot": chain["entrepot"]["id_entrepot"],
            "id_utilisateur": chain["utilisateur"]["id_utilisateur"]
        })
        response = client.put("/lots/LOT-INT-STATUT/statut", params={"statut": "en_alerte"})
        assert response.status_code == 200
        assert response.json()["statut"] == "en_alerte"

    def test_modifier_statut_perime(self, client):
        chain = _creer_chain_complete(client)
        client.post("/lots", json={
            "id_lot": "LOT-INT-PERIME",
            "id_entrepot": chain["entrepot"]["id_entrepot"],
            "id_utilisateur": chain["utilisateur"]["id_utilisateur"]
        })
        response = client.put("/lots/LOT-INT-PERIME/statut", params={"statut": "perime"})
        assert response.status_code == 200
        assert response.json()["statut"] == "perime"

    def test_modifier_statut_lot_inexistant_404(self, client):
        response = client.put("/lots/LOT-INEXISTANT/statut", params={"statut": "perime"})
        assert response.status_code == 404

    def test_lots_tries_fifo(self, client):
        chain = _creer_chain_complete(client)
        client.post("/lots", json={
            "id_lot": "LOT-INT-FIFO-A",
            "id_entrepot": chain["entrepot"]["id_entrepot"],
            "id_utilisateur": chain["utilisateur"]["id_utilisateur"]
        })
        client.post("/lots", json={
            "id_lot": "LOT-INT-FIFO-B",
            "id_entrepot": chain["entrepot"]["id_entrepot"],
            "id_utilisateur": chain["utilisateur"]["id_utilisateur"]
        })
        lots = client.get("/lots").json()
        dates = [l["date_stockage"] for l in lots if l["id_lot"].startswith("LOT-INT-FIFO")]
        assert dates == sorted(dates)

    def test_creer_lot_champs_retournes(self, client):
        chain = _creer_chain_complete(client)
        response = client.post("/lots", json={
            "id_lot": "LOT-INT-CHAMPS",
            "id_entrepot": chain["entrepot"]["id_entrepot"],
            "id_utilisateur": chain["utilisateur"]["id_utilisateur"]
        })
        data = response.json()
        for champ in ["id_lot", "statut", "date_stockage", "id_entrepot", "id_utilisateur"]:
            assert champ in data, f"Champ manquant : {champ}"


# ════════════════════════════════════════════════════════════
# MESURES IoT
# ════════════════════════════════════════════════════════════

class TestMesures:

    @pytest.fixture(autouse=True)
    def setup_capteur_int(self):
        self.chain = _creer_chain_complete(
            TestClient(app, raise_server_exceptions=False)
        )

    def test_liste_mesures_retourne_liste(self, client):
        response = client.get("/mesures")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_dernieres_mesures_limite_respectee(self, client):
        response = client.get("/mesures/dernieres/5")
        assert response.status_code == 200
        assert len(response.json()) <= 5

    def test_dernieres_mesures_limite_1(self, client):
        response = client.get("/mesures/dernieres/1")
        assert response.status_code == 200
        assert len(response.json()) <= 1


# ════════════════════════════════════════════════════════════
# ALERTES MESURES
# ════════════════════════════════════════════════════════════

class TestAlertesMesures:

    @pytest.fixture(autouse=True)
    def cleanup(self):
        db = TestingSession()
        db.query(AlerteMesure).delete()
        db.commit()
        db.close()
        yield

    def test_liste_alertes_mesures_retourne_liste(self, client):
        response = client.get("/alertes-mesures")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_count_retourne_total_et_non_lues(self, client):
        response = client.get("/alertes/count")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "non_lues" in data

    def test_count_valeurs_numeriques(self, client):
        data = client.get("/alertes/count").json()
        assert isinstance(data["total"], int)
        assert isinstance(data["non_lues"], int)
        assert data["total"] >= 0
        assert data["non_lues"] >= 0

    def test_non_lues_retourne_liste(self, client):
        response = client.get("/alertes-mesures/non-lues")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_supprimer_alerte_inexistante_404(self, client):
        assert client.delete("/alertes-mesures/999999").status_code == 404

    def test_marquer_alerte_inexistante_lue_404(self, client):
        assert client.put("/alertes-mesures/999999/lue").status_code == 404

    def test_supprimer_toutes_alertes_mesures(self, client):
        assert client.delete("/alertes-mesures").status_code == 200

    def test_marquer_toutes_lues_retourne_message(self, client):
        response = client.put("/alertes-mesures/toutes/lues")
        assert response.status_code == 200
        assert "message" in response.json()

    def test_count_vide_apres_suppression(self, client):
        client.delete("/alertes")
        data = client.get("/alertes/count").json()
        assert data["total"] == 0

    def test_non_lues_vide_apres_marquer_toutes_lues(self, client):
        client.put("/alertes/toutes/lues")
        data = client.get("/alertes/count").json()
        assert data["non_lues"] == 0


# ════════════════════════════════════════════════════════════
# ALERTES LOTS
# ════════════════════════════════════════════════════════════

class TestAlertesLots:

    @pytest.fixture(autouse=True)
    def cleanup(self):
        db = TestingSession()
        db.query(AlerteLot).delete()
        db.commit()
        db.close()
        yield

    def test_liste_alertes_lots_retourne_liste(self, client):
        response = client.get("/alertes-lots")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_creer_alerte_lot(self, client):
        chain = _creer_chain_complete(client)
        client.post("/lots", json={
            "id_lot": "LOT-ALERT-TEST",
            "id_entrepot": chain["entrepot"]["id_entrepot"],
            "id_utilisateur": chain["utilisateur"]["id_utilisateur"]
        })
        response = client.post("/alertes-lots", json={
            "message": "Lot perime detecte",
            "id_lot": "LOT-ALERT-TEST"
        })
        assert response.status_code == 201
        assert response.json()["statut"] == "non_lue"


# ════════════════════════════════════════════════════════════
# UTILISATEURS
# ════════════════════════════════════════════════════════════

class TestUtilisateurs:

    @pytest.fixture(autouse=True)
    def cleanup(self):
        db = TestingSession()
        db.query(Utilisateur).delete()
        db.commit()
        db.close()
        yield

    def test_creer_utilisateur(self, client):
        response = client.post("/utilisateurs", json={
            "nom": "Test",
            "prenom": "User",
            "email": "test.user@example.com",
            "mot_de_passe": "password123"
        })
        assert response.status_code == 201
        assert response.json()["email"] == "test.user@example.com"
        assert response.json()["actif"] is True

    def test_email_doublon_retourne_409(self, client):
        client.post("/utilisateurs", json={
            "nom": "A", "prenom": "B", "email": "dup@test.com", "mot_de_passe": "p"
        })
        response = client.post("/utilisateurs", json={
            "nom": "C", "prenom": "D", "email": "dup@test.com", "mot_de_passe": "p"
        })
        assert response.status_code == 409

    def test_lister_utilisateurs(self, client):
        response = client.get("/utilisateurs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_lire_utilisateur_par_id(self, client):
        resp = client.post("/utilisateurs", json={
            "nom": "Read", "prenom": "Test", "email": "read@test.com", "mot_de_passe": "p"
        })
        uid = resp.json()["id_utilisateur"]
        response = client.get(f"/utilisateurs/{uid}")
        assert response.status_code == 200
        assert response.json()["email"] == "read@test.com"

    def test_utilisateur_inexistant_retourne_404(self, client):
        assert client.get("/utilisateurs/99999").status_code == 404