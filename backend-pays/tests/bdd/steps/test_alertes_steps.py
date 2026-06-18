"""
Steps pytest-bdd — Feature: Gestion des alertes
"""
import pytest
from pytest_bdd import given, when, then, parsers, scenarios

from models import Alerte

scenarios("../features/alertes.feature")


# ── Stockage de l'id d'alerte créée entre les steps ─────────
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
def alerte_non_lue(client):
    resp = client.post("/alertes", json={
        "type_alerte": "temperature",
        "message": "Température élevée détectée",
        "valeur": 38.0,
        "seuil_min": 15.0,
        "seuil_max": 30.0
    })
    assert resp.status_code == 201, (
        f"Précondition échouée — impossible de créer l'alerte: {resp.text}"
    )
    return {"id": resp.json()["id"]}


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
def creer_alerte(client, type_alerte, message, valeur):
    return client.post("/alertes", json={
        "type_alerte": type_alerte,
        "message": message,
        "valeur": valeur
    })


@when("je consulte la liste des alertes", target_fixture="response")
def lister_alertes(client):
    return client.get("/alertes")


@when("je marque l'alerte comme lue", target_fixture="response")
def marquer_alerte_lue(client, alerte_context):
    alerte_id = alerte_context["id"]
    return client.patch(f"/alertes/{alerte_id}", json={"statut": "lue"})


# ════════════════════════════════════════════════════════════
# THEN
# ════════════════════════════════════════════════════════════

@then(parsers.parse("la réponse a le statut {status:d}"))
def verifier_statut(response, status):
    assert response.status_code == status, (
        f"Attendu {status}, reçu {response.status_code} — "
        f"body: {response.text}"
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
