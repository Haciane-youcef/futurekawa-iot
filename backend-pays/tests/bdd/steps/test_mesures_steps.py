"""
Steps pytest-bdd — Feature: Gestion des mesures IoT
"""
import pytest
from pytest_bdd import given, when, then, parsers, scenarios

from models import Mesure

# Lie ce fichier de steps à la feature correspondante
scenarios("../features/mesures.feature")


# ── Contexte partagé entre steps ────────────────────────────
@pytest.fixture
def context():
    return {}


# ════════════════════════════════════════════════════════════
# GIVEN
# ════════════════════════════════════════════════════════════

@given("l'API FutureKawa est démarrée")
def api_started(client):
    """Le client TestClient est injecté via la fixture conftest."""
    pass


@given("au moins une mesure existe en base")
def une_mesure_en_base(client):
    resp = client.post("/mesures", json={"temperature": 22.0, "humidite": 55.0})
    assert resp.status_code == 201


# ════════════════════════════════════════════════════════════
# WHEN
# ════════════════════════════════════════════════════════════

@when(
    parsers.parse(
        "je soumets une mesure avec température {temp:f} et humidité {hum:f}"
    ),
    target_fixture="response"
)
def soumettre_mesure(client, temp, hum):
    return client.post("/mesures", json={"temperature": temp, "humidite": hum})


@when("je soumets une mesure sans champ température", target_fixture="response")
def soumettre_mesure_sans_temp(client):
    return client.post("/mesures", json={"humidite": 60.0})


@when("je consulte la liste des mesures", target_fixture="response")
def lister_mesures(client):
    return client.get("/mesures")


# ════════════════════════════════════════════════════════════
# THEN
# ════════════════════════════════════════════════════════════

@then(parsers.parse("la réponse a le statut {status:d}"))
def verifier_statut(response, status):
    assert response.status_code == status, (
        f"Attendu {status}, reçu {response.status_code} — "
        f"body: {response.text}"
    )


@then("la mesure est bien enregistrée en base")
def mesure_enregistree(response):
    data = response.json()
    assert "id" in data
    assert data["id"] > 0


@then("la liste contient au moins une mesure")
def liste_non_vide(response):
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
