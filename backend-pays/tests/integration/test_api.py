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
os.environ["AUTH_REQUIRED"] = "false"
os.environ["JWT_SECRET"]    = "test-secret"

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from jose import jwt as jose_jwt
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
# Token JWT de test pour les routes protégées
# ─────────────────────────────────────────────────────────────

JWT_SECRET = "test-secret"


def _make_auth_header(utilisateur_id):
    """Génère un header Authorization avec un token contenant le bon user."""
    token = jose_jwt.encode(
        {"sub": str(utilisateur_id), "email": "test@futurekawa.com"},
        JWT_SECRET,
        algorithm="HS256"
    )
    return {"Authorization": f"Bearer {token}"}


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
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine_test)
    Base.metadata.create_all(bind=engine_test)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine_test)
    engine_test.dispose()
    app.dependency_overrides.clear()
    if os.path.exists("futurekawa_integration_test.db"):
        os.remove("futurekawa_integration_test.db")


# ─────────────────────────────────────────────────────────────
# Utilitaire : récupérer l'ID d'une réponse JSON
# ─────────────────────────────────────────────────────────────

def _get_id(data: dict, *keys):
    """Récupère la première clé trouvée dans le dict parmi keys."""
    for k in keys:
        if k in data:
            return data[k]
    return None


# ─────────────────────────────────────────────────────────────
# Helper : créer la chaîne complète config → exploitation
# → entrepot → capteur → utilisateur
# ─────────────────────────────────────────────────────────────

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
    """
    Crée ou récupère la chaîne complète de FK.
    Idempotent : si la config existe déjà, la récupère via GET.
    """
    # ── Config (créer ou récupérer) ──────────────────────────
    cfg_resp = client.post("/config", json=CONFIG_BRESIL)
    if cfg_resp.status_code == 200:
        cfg = cfg_resp.json()
    elif cfg_resp.status_code == 400:
        cfg = client.get("/config").json()
    else:
        raise RuntimeError(f"Impossible de créer la config: {cfg_resp.status_code} {cfg_resp.text}")

    config_id = _get_id(cfg, "id_config", "id")

    # ── Exploitation ────────────────────────────────────────
    exploitations = client.get("/exploitations").json()
    expl_id = None
    for e in exploitations:
        if e.get("nom") == "Exploitation Alto Paraiso":
            expl_id = _get_id(e, "id_exploitation", "id")
            break

    if expl_id is None:
        expl_resp = client.post("/exploitations", json={
            "nom": "Exploitation Alto Paraiso",
            "id_config": config_id
        })
        assert expl_resp.status_code == 201, (
            f"Création exploitation échouée: {expl_resp.text}"
        )
        expl = expl_resp.json()
        expl_id = _get_id(expl, "id_exploitation", "id")
    else:
        expl = client.get(f"/exploitations/{expl_id}").json()

    # ── Entrepot ────────────────────────────────────────────
    entrepots = client.get("/entrepots").json()
    ent_id = None
    for e in entrepots:
        if e.get("nom") == "Entrepot Goias":
            ent_id = _get_id(e, "id_entrepot", "id")
            break

    if ent_id is None:
        ent_resp = client.post("/entrepots", json={
            "nom": "Entrepot Goias",
            "localisation": "Goias, Bresil",
            "id_exploitation": expl_id
        })
        assert ent_resp.status_code == 201, (
            f"Création entrepot échouée: {ent_resp.text}"
        )
        ent = ent_resp.json()
        ent_id = _get_id(ent, "id_entrepot", "id")
    else:
        ent = client.get(f"/entrepots/{ent_id}").json()

    # ── Capteur ─────────────────────────────────────────────
    capteurs = client.get("/capteurs").json()
    cap_id = None
    for c in capteurs:
        if c.get("reference") == "CAP-INT-001":
            cap_id = _get_id(c, "id_capteur", "id")
            break

    if cap_id is None:
        cap_resp = client.post("/capteurs", json={
            "type_capteur": "temperature_humidite",
            "reference": "CAP-INT-001",
            "id_entrepot": ent_id
        })
        assert cap_resp.status_code == 201, (
            f"Création capteur échouée: {cap_resp.text}"
        )
        cap = cap_resp.json()
        cap_id = _get_id(cap, "id_capteur", "id")
    else:
        cap = client.get(f"/capteurs/{cap_id}").json()

    # ── Utilisateur ─────────────────────────────────────────
    utilisateurs = client.get("/utilisateurs").json()
    usr_id = None
    for u in utilisateurs:
        if u.get("email") == "maria@test.com":
            usr_id = _get_id(u, "id_utilisateur", "id")
            break

    if usr_id is None:
        usr_resp = client.post("/utilisateurs", json={
            "nom": "Silva",
            "prenom": "Maria",
            "email": "maria@test.com",
            "mot_de_passe": "pwd123"
        })
        assert usr_resp.status_code == 201, (
            f"Création utilisateur échouée: {usr_resp.text}"
        )
        usr = usr_resp.json()
        usr_id = _get_id(usr, "id_utilisateur", "id")
    else:
        usr = client.get(f"/utilisateurs/{usr_id}").json()

    return {
        "config": cfg,
        "config_id": config_id,
        "exploitation": expl,
        "exploitation_id": expl_id,
        "entrepot": ent,
        "entrepot_id": ent_id,
        "capteur": cap,
        "capteur_id": cap_id,
        "utilisateur": usr,
        "utilisateur_id": usr_id,
    }


# ════════════════════════════════════════════════════════════
# SANTÉ DE L'API
# ════════════════════════════════════════════════════════════

class TestSanteAPI:
    """Vérifie que l'API démarre et répond correctement."""

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
        config_id = _get_id(cfg, "id_config", "id")
        response = client.post("/exploitations", json={
            "nom": "Fazenda Boa Vista",
            "id_config": config_id
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
            "id_exploitation": chain["exploitation_id"]
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
            "id_entrepot": chain["entrepot_id"]
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
    """CRUD complet sur l'endpoint /lots."""

    @pytest.fixture(autouse=True)
    def cleanup_lots(self):
        """Lots de test supprimés avant chaque test."""
        db = TestingSession()
        db.query(Lot).filter(Lot.id_lot.like("LOT-INT-%")).delete(synchronize_session=False)
        db.commit()
        db.close()
        yield

    def _headers(self, chain):
        """Retourne les headers auth avec l'utilisateur de la chaîne."""
        return _make_auth_header(chain["utilisateur_id"])

    def test_creer_lot_valide(self, client):
        chain = _creer_chain_complete(client)
        response = client.post("/lots", json={
            "id_lot": "LOT-INT-001",
            "id_entrepot": chain["entrepot_id"],
            "id_utilisateur": chain["utilisateur_id"]
        }, headers=self._headers(chain))
        assert response.status_code == 201
        data = response.json()
        assert _get_id(data, "id_lot", "lot_id") == "LOT-INT-001"
        assert data["statut"] == "conforme"

    def test_lot_cree_contient_date_stockage(self, client):
        chain = _creer_chain_complete(client)
        response = client.post("/lots", json={
            "id_lot": "LOT-INT-DATE",
            "id_entrepot": chain["entrepot_id"],
            "id_utilisateur": chain["utilisateur_id"]
        }, headers=self._headers(chain))
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
            "id_entrepot": chain["entrepot_id"],
            "id_utilisateur": chain["utilisateur_id"]
        }, headers=self._headers(chain))
        lot_ids = [_get_id(l, "id_lot", "lot_id") for l in client.get("/lots").json()]
        assert "LOT-INT-VISIBLE" in lot_ids

    def test_lire_lot_par_id(self, client):
        chain = _creer_chain_complete(client)
        client.post("/lots", json={
            "id_lot": "LOT-INT-READ",
            "id_entrepot": chain["entrepot_id"],
            "id_utilisateur": chain["utilisateur_id"]
        }, headers=self._headers(chain))
        response = client.get("/lots/LOT-INT-READ")
        assert response.status_code == 200
        assert _get_id(response.json(), "id_lot", "lot_id") == "LOT-INT-READ"

    def test_lot_inexistant_retourne_404(self, client):
        assert client.get("/lots/LOT-INEXISTANT-99999").status_code == 404

    def test_lot_id_doublon_retourne_erreur(self, client):
        chain = _creer_chain_complete(client)
        payload = {
            "id_lot": "LOT-INT-DUPL",
            "id_entrepot": chain["entrepot_id"],
            "id_utilisateur": chain["utilisateur_id"]
        }
        client.post("/lots", json=payload, headers=self._headers(chain))
        response = client.post("/lots", json=payload, headers=self._headers(chain))
        assert response.status_code in [400, 409, 422, 500]

    def test_modifier_statut_en_alerte(self, client):
        chain = _creer_chain_complete(client)
        client.post("/lots", json={
            "id_lot": "LOT-INT-STATUT",
            "id_entrepot": chain["entrepot_id"],
            "id_utilisateur": chain["utilisateur_id"]
        }, headers=self._headers(chain))
        response = client.put(
            "/lots/LOT-INT-STATUT/statut",
            params={"statut": "en_alerte"},
            headers=self._headers(chain)
        )
        assert response.status_code == 200
        assert response.json()["statut"] == "en_alerte"

    def test_modifier_statut_perime(self, client):
        chain = _creer_chain_complete(client)
        client.post("/lots", json={
            "id_lot": "LOT-INT-PERIME",
            "id_entrepot": chain["entrepot_id"],
            "id_utilisateur": chain["utilisateur_id"]
        }, headers=self._headers(chain))
        response = client.put(
            "/lots/LOT-INT-PERIME/statut",
            params={"statut": "perime"},
            headers=self._headers(chain)
        )
        assert response.status_code == 200
        assert response.json()["statut"] == "perime"

    def test_modifier_statut_lot_inexistant_404(self, client):
        chain = _creer_chain_complete(client)
        response = client.put(
            "/lots/LOT-INEXISTANT/statut",
            params={"statut": "perime"},
            headers=self._headers(chain)
        )
        assert response.status_code == 404

    def test_lots_tries_fifo(self, client):
        chain = _creer_chain_complete(client)
        client.post("/lots", json={
            "id_lot": "LOT-INT-FIFO-A",
            "id_entrepot": chain["entrepot_id"],
            "id_utilisateur": chain["utilisateur_id"]
        }, headers=self._headers(chain))
        client.post("/lots", json={
            "id_lot": "LOT-INT-FIFO-B",
            "id_entrepot": chain["entrepot_id"],
            "id_utilisateur": chain["utilisateur_id"]
        }, headers=self._headers(chain))
        lots = client.get("/lots").json()
        dates = [
            l["date_stockage"] for l in lots
            if _get_id(l, "id_lot", "lot_id", "").startswith("LOT-INT-FIFO")
        ]
        assert dates == sorted(dates)

    def test_creer_lot_champs_retournes(self, client):
        chain = _creer_chain_complete(client)
        response = client.post("/lots", json={
            "id_lot": "LOT-INT-CHAMPS",
            "id_entrepot": chain["entrepot_id"],
            "id_utilisateur": chain["utilisateur_id"]
        }, headers=self._headers(chain))
        data = response.json()
        for champ in ["statut", "date_stockage"]:
            assert champ in data, f"Champ manquant : {champ}"


# ════════════════════════════════════════════════════════════
# MESURES IoT
# ════════════════════════════════════════════════════════════

class TestMesures:
    """Endpoints de lecture des mesures IoT."""

    @pytest.fixture(autouse=True)
    def ensure_chain(self, client):
        """S'assure que la chaîne de FK existe pour tous les tests."""
        _creer_chain_complete(client)
        yield

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
    """Endpoints CRUD des alertes mesures."""

    @pytest.fixture(autouse=True)
    def cleanup_alertes(self):
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
        headers = _make_auth_header(chain["utilisateur_id"])
        client.post("/lots", json={
            "id_lot": "LOT-ALERT-TEST",
            "id_entrepot": chain["entrepot_id"],
            "id_utilisateur": chain["utilisateur_id"]
        }, headers=headers)
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
        uid = _get_id(resp.json(), "id_utilisateur", "id")
        response = client.get(f"/utilisateurs/{uid}")
        assert response.status_code == 200
        assert response.json()["email"] == "read@test.com"

    def test_utilisateur_inexistant_retourne_404(self, client):
        assert client.get("/utilisateurs/99999").status_code == 404