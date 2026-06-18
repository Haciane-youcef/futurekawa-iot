"""
Steps pytest-bdd — Feature: Gestion des lots de café
"""
import pytest
from pytest_bdd import given, when, then, parsers, scenarios

from models import Lot

scenarios("../features/lots.feature")


# ════════════════════════════════════════════════════════════
# GIVEN
# ════════════════════════════════════════════════════════════

@given("l'API FutureKawa est démarrée")
def api_started(client):
    pass


@given(
    parsers.parse('le lot "{lot_id}" existe déjà en base')
)
def lot_existant(client, lot_id, setup_entrepot, setup_utilisateur):
    entrepot_id = setup_entrepot["id_entrepot"]
    utilisateur_id = setup_utilisateur["id_utilisateur"]
    resp = client.post("/lots", json={
        "id_lot": lot_id,
        "id_entrepot": entrepot_id,
        "id_utilisateur": utilisateur_id
    })
    assert resp.status_code == 201, (
        f"Précondition échouée — impossible de créer {lot_id}: {resp.text}"
    )


# ════════════════════════════════════════════════════════════
# WHEN
# ════════════════════════════════════════════════════════════

@when(
    parsers.parse(
        'je crée un lot avec lot_id "{lot_id}", pays "{pays}", '
        'exploitation "{exploitation}", entrepot "{entrepot}"'
    ),
    target_fixture="response"
)
def creer_lot(client, lot_id, pays, exploitation, entrepot,
              setup_entrepot, setup_utilisateur):
    entrepot_id = setup_entrepot["id_entrepot"]
    utilisateur_id = setup_utilisateur["id_utilisateur"]
    return client.post("/lots", json={
        "id_lot": lot_id,
        "id_entrepot": entrepot_id,
        "id_utilisateur": utilisateur_id
    })


@when("je consulte la liste des lots", target_fixture="response")
def lister_lots(client):
    return client.get("/lots")


# ════════════════════════════════════════════════════════════
# THEN
# ════════════════════════════════════════════════════════════

@then(parsers.parse("la réponse a le statut {status:d}"))
def verifier_statut(response, status):
    assert response.status_code == status, (
        f"Attendu {status}, reçu {response.status_code} — body: {response.text}"
    )


@then(parsers.parse('le lot "{lot_id}" est bien enregistré'))
def lot_enregistre(response, lot_id):
    data = response.json()
    assert data.get("id_lot") == lot_id


@then("la liste contient au moins un lot")
def liste_non_vide(response):
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1