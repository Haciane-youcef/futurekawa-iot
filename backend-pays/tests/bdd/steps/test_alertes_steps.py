"""
Steps pytest-bdd — Feature: Gestion des alertes
"""
import pytest
from pytest_bdd import given, when, then, parsers, scenarios

from models import AlerteMesure

scenarios("../features/alertes.feature")


@pytest.fixture
def alerte_context():
    return {"id": None}


# ════════════════════════════════════════════════════════════
# GIVEN
# ════════════════════════════════════════════════════════════

@given("l'API FutureKawa est démarrée")
def api_started(client):
    pass


@given("une alerte non lue existe en base", target_fixture="alerte_context")
def alerte_non_lue(client, setup_capteur):
    # Créer une mesure pour avoir un id_mesure valide
    capteur_id = setup_capteur["id_capteur"]
    mesure_resp = client.post("/mesures", json={
        "temperature": 22.0,
        "humidite": 55.0,
        "id_capteur": capteur_id
    })
    assert mesure_resp.status_code == 201
    mesure_id = mesure_resp.json()["id_mesure"]

    resp = client.post("/alertes-mesures", json={
        "type_alerte": "temperature",
        "message": "Température élevée détectée",
        "valeur_mesuree": 38.0,
        "seuil_min": 15.0,
        "seuil_max": 30.0,
        "id_mesure": mesure_id
    })
    assert resp.status_code == 201, (
        f"Précondition échouée — impossible de créer l'alerte: {resp.text}"
    )
    return {"id": resp.json()["id_alerte_mesure"]}


# ════════════════════════════════════════════════════════════
# WHEN
# ════════════════════════════════════════════════════════════

@when(
    parsers.parse(
        'je crée une alerte de type "{type_alerte}" '
        'avec message "{message}" et valeur {valeur:f}'
    ),
    target_fixture="response"
)
def creer_alerte(client, type_alerte, message, valeur, setup_capteur):
    capteur_id = setup_capteur["id_capteur"]
    mesure_resp = client.post("/mesures", json={
        "temperature": 22.0,
        "humidite": 55.0,
        "id_capteur": capteur_id
    })
    mesure_id = mesure_resp.json()["id_mesure"]

    return client.post("/alertes-mesures", json={
        "type_alerte": type_alerte,
        "message": message,
        "valeur_mesuree": valeur,
        "seuil_min": 15.0,
        "seuil_max": 30.0,
        "id_mesure": mesure_id
    })


@when("je consulte la liste des alertes", target_fixture="response")
def lister_alertes(client):
    return client.get("/alertes-mesures")


@when("je marque l'alerte comme lue", target_fixture="response")
def marquer_alerte_lue(client, alerte_context):
    alerte_id = alerte_context["id"]
    return client.patch(f"/alertes-mesures/{alerte_id}", json={"statut": "lue"})


# ════════════════════════════════════════════════════════════
# THEN
# ════════════════════════════════════════════════════════════

@then(parsers.parse("la réponse a le statut {status:d}"))
def verifier_statut(response, status):
    assert response.status_code == status, (
        f"Attendu {status}, reçu {response.status_code} — body: {response.text}"
    )


@then(parsers.parse('l\'alerte a le statut "{statut}"'))
def verifier_statut_alerte(response, statut):
    data = response.json()
    assert data.get("statut") == statut, (
        f"Attendu statut='{statut}', reçu '{data.get('statut')}'"
    )


@then("la liste contient au moins une alerte")
def liste_non_vide(response):
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1