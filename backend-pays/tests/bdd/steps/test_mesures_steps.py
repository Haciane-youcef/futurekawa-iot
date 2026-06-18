"""
Steps pytest-bdd — Feature: Gestion des mesures IoT
"""
import pytest
from pytest_bdd import given, when, then, parsers, scenarios

from models import Mesure

scenarios("../features/mesures.feature")


@pytest.fixture
def context():
    return {}


# ════════════════════════════════════════════════════════════
# GIVEN
# ════════════════════════════════════════════════════════════

@given("l'API FutureKawa est démarrée")
def api_started(client):
    pass


@given("au moins une mesure existe en base")
def une_mesure_en_base(client, setup_capteur):
    capteur_id = setup_capteur["id_capteur"]
    resp = client.post("/mesures", json={
        "temperature": 22.0,
        "humidite": 55.0,
        "id_capteur": capteur_id
    })
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
def soumettre_mesure(client, temp, hum, setup_capteur):
    capteur_id = setup_capteur["id_capteur"]
    return client.post("/mesures", json={
        "temperature": temp,
        "humidite": hum,
        "id_capteur": capteur_id
    })


@when("je soumets une mesure sans champ température", target_fixture="response")
def soumettre_mesure_sans_temp(client, setup_capteur):
    capteur_id = setup_capteur["id_capteur"]
    return client.post("/mesures", json={"humidite": 60.0, "id_capteur": capteur_id})


@when("je consulte la liste des mesures", target_fixture="response")
def lister_mesures(client):
    return client.get("/mesures")


# ════════════════════════════════════════════════════════════
# THEN
# ════════════════════════════════════════════════════════════

@then(parsers.parse("la réponse a le statut {status:d}"))
def verifier_statut(response, status):
    assert response.status_code == status, (
        f"Attendu {status}, reçu {response.status_code} — body: {response.text}"
    )


@then("la mesure est bien enregistrée en base")
def mesure_enregistree(response):
    data = response.json()
    assert "id_mesure" in data
    assert data["id_mesure"] > 0


@then("la liste contient au moins une mesure")
def liste_non_vide(response):
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1