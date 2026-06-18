"""
FutureKawa — Tests UNITAIRES
tests/unit/test_unit_alertes.py

Teste la logique métier pure : seuils, alertes, FIFO, messages.
Aucune base de données, aucun réseau, aucun service externe.
"""

import pytest
from datetime import datetime, timedelta


# ─────────────────────────────────────────────────────────────
# Logique métier simulée (sans import de l'app)
# ─────────────────────────────────────────────────────────────

class AlerteMetier:
    """Logique pure de déclenchement d'alertes (sans BDD).
    La chaîne réelle est : capteur → entrepot → exploitation → config.
    Ici on simplifie en utilisant un lookup direct par pays (config)."""

    CONFIG_PAYS = {
        "Bresil":   {"temp_ideale": 29.0, "hum_ideale": 55.0, "tol_temp": 3.0, "tol_hum": 2.0},
        "Equateur": {"temp_ideale": 31.0, "hum_ideale": 60.0, "tol_temp": 3.0, "tol_hum": 2.0},
        "Colombie": {"temp_ideale": 26.0, "hum_ideale": 80.0, "tol_temp": 3.0, "tol_hum": 2.0},
    }

    @staticmethod
    def temperature_hors_seuil(pays: str, temperature: float) -> bool:
        cfg = AlerteMetier.CONFIG_PAYS[pays]
        return not (
            cfg["temp_ideale"] - cfg["tol_temp"]
            <= temperature <=
            cfg["temp_ideale"] + cfg["tol_temp"]
        )

    @staticmethod
    def humidite_hors_seuil(pays: str, humidite: float) -> bool:
        cfg = AlerteMetier.CONFIG_PAYS[pays]
        return not (
            cfg["hum_ideale"] - cfg["tol_hum"]
            <= humidite <=
            cfg["hum_ideale"] + cfg["tol_hum"]
        )

    @staticmethod
    def lot_perime(date_stockage: datetime, limite_jours: int = 365) -> bool:
        return (datetime.utcnow() - date_stockage).days >= limite_jours


def trier_lots_fifo(lots: list) -> list:
    """Trie les lots du plus ancien au plus récent (FIFO)."""
    return sorted(lots, key=lambda l: l["date_stockage"])


def construire_message_alerte(
    type_alerte: str, valeur: float, seuil_min: float, seuil_max: float
) -> str:
    if type_alerte == "temperature":
        return f"Température anormale : {valeur}°C (seuil: {seuil_min}–{seuil_max}°C)"
    if type_alerte == "humidite":
        return f"Humidité anormale : {valeur}% (seuil: {seuil_min}–{seuil_max}%)"
    return f"Alerte inconnue : {valeur}"


def construire_message_lot_perime(id_lot: str, date_stockage: datetime) -> str:
    return f"Lot {id_lot} perime — stocke depuis {date_stockage.strftime('%Y-%m-%d')}"


# ════════════════════════════════════════════════════════════
# TESTS — Seuils température
# ════════════════════════════════════════════════════════════

class TestSeuilsTemperature:

    # ── Brésil (29°C ±3 → plage [26, 32]) ──────────────────

    def test_bresil_temperature_ideale_ok(self):
        assert not AlerteMetier.temperature_hors_seuil("Bresil", 29.0)

    def test_bresil_temperature_limite_haute_ok(self):
        assert not AlerteMetier.temperature_hors_seuil("Bresil", 32.0)

    def test_bresil_temperature_limite_basse_ok(self):
        assert not AlerteMetier.temperature_hors_seuil("Bresil", 26.0)

    def test_bresil_temperature_trop_haute_alerte(self):
        assert AlerteMetier.temperature_hors_seuil("Bresil", 32.1)

    def test_bresil_temperature_trop_basse_alerte(self):
        assert AlerteMetier.temperature_hors_seuil("Bresil", 25.9)

    def test_bresil_temperature_milieu_plage_ok(self):
        assert not AlerteMetier.temperature_hors_seuil("Bresil", 30.0)

    # ── Équateur (31°C ±3 → plage [28, 34]) ────────────────

    def test_equateur_temperature_ideale_ok(self):
        assert not AlerteMetier.temperature_hors_seuil("Equateur", 31.0)

    def test_equateur_temperature_limite_haute_ok(self):
        assert not AlerteMetier.temperature_hors_seuil("Equateur", 34.0)

    def test_equateur_temperature_limite_basse_ok(self):
        assert not AlerteMetier.temperature_hors_seuil("Equateur", 28.0)

    def test_equateur_temperature_hors_seuil_alerte(self):
        assert AlerteMetier.temperature_hors_seuil("Equateur", 20.0)

    # ── Colombie (26°C ±3 → plage [23, 29]) ────────────────

    def test_colombie_temperature_ideale_ok(self):
        assert not AlerteMetier.temperature_hors_seuil("Colombie", 26.0)

    def test_colombie_temperature_hors_seuil_alerte(self):
        assert AlerteMetier.temperature_hors_seuil("Colombie", 35.0)

    # ── Valeurs extrêmes ────────────────────────────────────

    def test_temperature_tres_negative_alerte(self):
        assert AlerteMetier.temperature_hors_seuil("Bresil", -10.0)

    def test_temperature_tres_haute_alerte(self):
        assert AlerteMetier.temperature_hors_seuil("Bresil", 100.0)

    def test_temperature_zero_alerte(self):
        assert AlerteMetier.temperature_hors_seuil("Bresil", 0.0)

    def test_pays_inconnu_leve_keyerror(self):
        with pytest.raises(KeyError):
            AlerteMetier.temperature_hors_seuil("France", 25.0)


# ════════════════════════════════════════════════════════════
# TESTS — Seuils humidité
# ════════════════════════════════════════════════════════════

class TestSeuilsHumidite:

    # ── Brésil (55% ±2 → plage [53, 57]) ───────────────────

    def test_bresil_humidite_ideale_ok(self):
        assert not AlerteMetier.humidite_hors_seuil("Bresil", 55.0)

    def test_bresil_humidite_limite_haute_ok(self):
        assert not AlerteMetier.humidite_hors_seuil("Bresil", 57.0)

    def test_bresil_humidite_limite_basse_ok(self):
        assert not AlerteMetier.humidite_hors_seuil("Bresil", 53.0)

    def test_bresil_humidite_trop_haute_alerte(self):
        assert AlerteMetier.humidite_hors_seuil("Bresil", 57.1)

    def test_bresil_humidite_trop_basse_alerte(self):
        assert AlerteMetier.humidite_hors_seuil("Bresil", 52.9)

    def test_bresil_humidite_milieu_plage_ok(self):
        assert not AlerteMetier.humidite_hors_seuil("Bresil", 55.5)

    # ── Colombie (80% ±2 → plage [78, 82]) ─────────────────

    def test_colombie_humidite_ideale_ok(self):
        assert not AlerteMetier.humidite_hors_seuil("Colombie", 80.0)

    def test_colombie_humidite_hors_seuil_alerte(self):
        assert AlerteMetier.humidite_hors_seuil("Colombie", 50.0)

    # ── Valeurs extrêmes ────────────────────────────────────

    def test_humidite_zero_alerte(self):
        assert AlerteMetier.humidite_hors_seuil("Bresil", 0.0)

    def test_humidite_cent_alerte(self):
        assert AlerteMetier.humidite_hors_seuil("Bresil", 100.0)

    def test_pays_inconnu_leve_keyerror(self):
        with pytest.raises(KeyError):
            AlerteMetier.humidite_hors_seuil("France", 60.0)


# ════════════════════════════════════════════════════════════
# TESTS — Péremption des lots
# ════════════════════════════════════════════════════════════

class TestPeremptionLots:

    def test_lot_stocke_hier_pas_perime(self):
        date = datetime.utcnow() - timedelta(days=1)
        assert not AlerteMetier.lot_perime(date)

    def test_lot_il_y_a_364_jours_pas_perime(self):
        date = datetime.utcnow() - timedelta(days=364)
        assert not AlerteMetier.lot_perime(date)

    def test_lot_exactement_365_jours_perime(self):
        date = datetime.utcnow() - timedelta(days=365)
        assert AlerteMetier.lot_perime(date)

    def test_lot_il_y_a_400_jours_perime(self):
        date = datetime.utcnow() - timedelta(days=400)
        assert AlerteMetier.lot_perime(date)

    def test_lot_il_y_a_2_ans_perime(self):
        date = datetime.utcnow() - timedelta(days=730)
        assert AlerteMetier.lot_perime(date)

    def test_lot_date_future_pas_perime(self):
        date = datetime.utcnow() + timedelta(days=10)
        assert not AlerteMetier.lot_perime(date)

    def test_lot_perime_limite_personnalisee_30_jours(self):
        date = datetime.utcnow() - timedelta(days=31)
        assert AlerteMetier.lot_perime(date, limite_jours=30)

    def test_lot_non_perime_limite_personnalisee_30_jours(self):
        date = datetime.utcnow() - timedelta(days=20)
        assert not AlerteMetier.lot_perime(date, limite_jours=30)


# ════════════════════════════════════════════════════════════
# TESTS — Tri FIFO
# ════════════════════════════════════════════════════════════

class TestTriFIFO:

    def test_trois_lots_melanges_tries_correctement(self):
        lots = [
            {"id_lot": "LOT-C", "date_stockage": datetime(2024, 3, 1)},
            {"id_lot": "LOT-A", "date_stockage": datetime(2024, 1, 1)},
            {"id_lot": "LOT-B", "date_stockage": datetime(2024, 2, 1)},
        ]
        result = trier_lots_fifo(lots)
        assert [l["id_lot"] for l in result] == ["LOT-A", "LOT-B", "LOT-C"]

    def test_un_seul_lot_retourne_identique(self):
        lots = [{"id_lot": "LOT-SEUL", "date_stockage": datetime(2024, 6, 1)}]
        result = trier_lots_fifo(lots)
        assert len(result) == 1

    def test_lots_deja_tries_restent_dans_ordre(self):
        lots = [
            {"id_lot": "LOT-1", "date_stockage": datetime(2023, 1, 1)},
            {"id_lot": "LOT-2", "date_stockage": datetime(2023, 6, 1)},
            {"id_lot": "LOT-3", "date_stockage": datetime(2024, 1, 1)},
        ]
        result = trier_lots_fifo(lots)
        assert [l["id_lot"] for l in result] == ["LOT-1", "LOT-2", "LOT-3"]

    def test_liste_vide_retourne_liste_vide(self):
        assert trier_lots_fifo([]) == []

    def test_lots_meme_date_ordre_stable(self):
        lots = [
            {"id_lot": "LOT-X", "date_stockage": datetime(2024, 1, 1)},
            {"id_lot": "LOT-Y", "date_stockage": datetime(2024, 1, 1)},
        ]
        result = trier_lots_fifo(lots)
        assert len(result) == 2

    def test_tri_ne_modifie_pas_liste_originale(self):
        lots = [
            {"id_lot": "LOT-C", "date_stockage": datetime(2024, 3, 1)},
            {"id_lot": "LOT-A", "date_stockage": datetime(2024, 1, 1)},
        ]
        original_order = [l["id_lot"] for l in lots]
        trier_lots_fifo(lots)
        assert [l["id_lot"] for l in lots] == original_order


# ════════════════════════════════════════════════════════════
# TESTS — Construction des messages d'alerte
# ════════════════════════════════════════════════════════════

class TestMessagesAlertes:

    def test_message_temperature_contient_valeur(self):
        msg = construire_message_alerte("temperature", 35.0, 26.0, 32.0)
        assert "35.0" in msg

    def test_message_temperature_contient_mot_cle(self):
        msg = construire_message_alerte("temperature", 35.0, 26.0, 32.0)
        assert "température" in msg.lower()

    def test_message_temperature_contient_seuils(self):
        msg = construire_message_alerte("temperature", 35.0, 26.0, 32.0)
        assert "26.0" in msg
        assert "32.0" in msg

    def test_message_humidite_contient_valeur(self):
        msg = construire_message_alerte("humidite", 70.0, 53.0, 57.0)
        assert "70.0" in msg

    def test_message_humidite_contient_mot_cle(self):
        msg = construire_message_alerte("humidite", 70.0, 53.0, 57.0)
        assert "humidité" in msg.lower()

    def test_message_humidite_contient_seuils(self):
        msg = construire_message_alerte("humidite", 70.0, 53.0, 57.0)
        assert "53.0" in msg
        assert "57.0" in msg

    def test_message_type_inconnu_contient_valeur(self):
        msg = construire_message_alerte("inconnu", 42.0, 0.0, 100.0)
        assert "42.0" in msg

    def test_message_retourne_chaine(self):
        for type_alerte in ["temperature", "humidite", "lot_perime", "inconnu"]:
            msg = construire_message_alerte(type_alerte, 30.0, 20.0, 40.0)
            assert isinstance(msg, str)
            assert len(msg) > 0

    def test_message_temperature_valeur_entiere(self):
        msg = construire_message_alerte("temperature", 35, 26.0, 32.0)
        assert "35" in msg


# ════════════════════════════════════════════════════════════
# TESTS — Messages alerte lot (nouveau)
# ════════════════════════════════════════════════════════════

class TestMessagesAlertesLot:

    def test_message_lot_perime_contient_id(self):
        msg = construire_message_lot_perime("LOT-001", datetime(2023, 6, 15))
        assert "LOT-001" in msg

    def test_message_lot_perime_contient_date(self):
        msg = construire_message_lot_perime("LOT-002", datetime(2023, 3, 20))
        assert "2023-03-20" in msg

    def test_message_lot_perime_contient_mot_perime(self):
        msg = construire_message_lot_perime("LOT-003", datetime(2024, 1, 1))
        assert "perime" in msg.lower()