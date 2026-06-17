"""
FutureKawa — Tests UNITAIRES
tests/unit/test_unit_alertes.py

Teste la logique métier pure : seuils, alertes, FIFO, messages.
Aucune base de données, aucun réseau, aucun service externe.

NOTE : Ce fichier remplace les classes TestLogiqueSeuils et
TestLogiqueLotsPerimes de test_models_and_logic.py — supprimer
ces deux classes là-bas pour éviter les doublons.
"""

import pytest
from datetime import datetime, timedelta


# ─────────────────────────────────────────────────────────────
# Logique métier simulée (sans import de l'app)
# ─────────────────────────────────────────────────────────────

class AlerteMetier:
    """Logique pure de déclenchement d'alertes (sans BDD)."""

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
        """
        Un lot est périmé si (aujourd'hui - date_stockage) >= limite_jours.
        Règle : >= 365 jours → périmé (la limite EST incluse).
        Cohérent avec test_lot_exactement_365_jours_perime ci-dessous.
        """
        return (datetime.utcnow() - date_stockage).days >= limite_jours


def trier_lots_fifo(lots: list) -> list:
    """Trie les lots du plus ancien au plus récent (FIFO)."""
    return sorted(lots, key=lambda l: l["date_stockage"])


def construire_message_alerte(
    type_alerte: str, valeur: float, seuil_min: float, seuil_max: float
) -> str:
    """Construit le message d'alerte (logique pure)."""
    if type_alerte == "temperature":
        return f"Température anormale : {valeur}°C (seuil: {seuil_min}–{seuil_max}°C)"
    if type_alerte == "humidite":
        return f"Humidité anormale : {valeur}% (seuil: {seuil_min}–{seuil_max}%)"
    return f"Alerte inconnue : {valeur}"


# ════════════════════════════════════════════════════════════
# TESTS — Seuils température
# ════════════════════════════════════════════════════════════

class TestSeuilsTemperature:
    """
    Vérifie la logique temperature_hors_seuil pour tous les pays.
    Couvre : valeur idéale, limites exactes, dépassements, valeurs extrêmes.
    """

    # ── Brésil (29°C ±3 → plage [26, 32]) ──────────────────

    def test_bresil_temperature_ideale_ok(self):
        """29°C est exactement la valeur idéale → pas d'alerte."""
        assert not AlerteMetier.temperature_hors_seuil("Bresil", 29.0)

    def test_bresil_temperature_limite_haute_ok(self):
        """32°C est à la limite haute incluse → pas d'alerte."""
        assert not AlerteMetier.temperature_hors_seuil("Bresil", 32.0)

    def test_bresil_temperature_limite_basse_ok(self):
        """26°C est à la limite basse incluse → pas d'alerte."""
        assert not AlerteMetier.temperature_hors_seuil("Bresil", 26.0)

    def test_bresil_temperature_trop_haute_alerte(self):
        """32.1°C dépasse d'un dixième la limite haute → alerte."""
        assert AlerteMetier.temperature_hors_seuil("Bresil", 32.1)

    def test_bresil_temperature_trop_basse_alerte(self):
        """25.9°C est juste sous la limite basse → alerte."""
        assert AlerteMetier.temperature_hors_seuil("Bresil", 25.9)

    def test_bresil_temperature_milieu_plage_ok(self):
        """30°C est au milieu de la plage Brésil → pas d'alerte."""
        assert not AlerteMetier.temperature_hors_seuil("Bresil", 30.0)

    # ── Équateur (31°C ±3 → plage [28, 34]) ────────────────

    def test_equateur_temperature_ideale_ok(self):
        """31°C est la valeur idéale Équateur → pas d'alerte."""
        assert not AlerteMetier.temperature_hors_seuil("Equateur", 31.0)

    def test_equateur_temperature_limite_haute_ok(self):
        """34°C est à la limite haute Équateur → pas d'alerte."""
        assert not AlerteMetier.temperature_hors_seuil("Equateur", 34.0)

    def test_equateur_temperature_limite_basse_ok(self):
        """28°C est à la limite basse Équateur → pas d'alerte."""
        assert not AlerteMetier.temperature_hors_seuil("Equateur", 28.0)

    def test_equateur_temperature_hors_seuil_alerte(self):
        """20°C est très loin de 31°C ±3 → alerte."""
        assert AlerteMetier.temperature_hors_seuil("Equateur", 20.0)

    # ── Colombie (26°C ±3 → plage [23, 29]) ────────────────

    def test_colombie_temperature_ideale_ok(self):
        """26°C est la valeur idéale Colombie → pas d'alerte."""
        assert not AlerteMetier.temperature_hors_seuil("Colombie", 26.0)

    def test_colombie_temperature_hors_seuil_alerte(self):
        """35°C dépasse largement Colombie (26 ±3) → alerte."""
        assert AlerteMetier.temperature_hors_seuil("Colombie", 35.0)

    # ── Valeurs extrêmes (tous pays) ────────────────────────

    def test_temperature_tres_negative_alerte(self):
        """−10°C → toujours une alerte, peu importe le pays."""
        assert AlerteMetier.temperature_hors_seuil("Bresil", -10.0)

    def test_temperature_tres_haute_alerte(self):
        """100°C → toujours une alerte, peu importe le pays."""
        assert AlerteMetier.temperature_hors_seuil("Bresil", 100.0)

    def test_temperature_zero_alerte(self):
        """0°C → alerte (largement sous tous les seuils)."""
        assert AlerteMetier.temperature_hors_seuil("Bresil", 0.0)

    # ── Pays inconnu ────────────────────────────────────────

    def test_pays_inconnu_leve_keyerror(self):
        """Un pays non configuré doit lever KeyError, pas retourner silencieusement."""
        with pytest.raises(KeyError):
            AlerteMetier.temperature_hors_seuil("France", 25.0)


# ════════════════════════════════════════════════════════════
# TESTS — Seuils humidité
# ════════════════════════════════════════════════════════════

class TestSeuilsHumidite:
    """
    Vérifie la logique humidite_hors_seuil pour tous les pays.
    Couvre : valeur idéale, limites exactes, dépassements, valeurs extrêmes.
    """

    # ── Brésil (55% ±2 → plage [53, 57]) ───────────────────

    def test_bresil_humidite_ideale_ok(self):
        """55% est la valeur idéale Brésil → pas d'alerte."""
        assert not AlerteMetier.humidite_hors_seuil("Bresil", 55.0)

    def test_bresil_humidite_limite_haute_ok(self):
        """57% est à la limite haute incluse → pas d'alerte."""
        assert not AlerteMetier.humidite_hors_seuil("Bresil", 57.0)

    def test_bresil_humidite_limite_basse_ok(self):
        """53% est à la limite basse incluse → pas d'alerte."""
        assert not AlerteMetier.humidite_hors_seuil("Bresil", 53.0)

    def test_bresil_humidite_trop_haute_alerte(self):
        """57.1% dépasse la limite haute d'un dixième → alerte."""
        assert AlerteMetier.humidite_hors_seuil("Bresil", 57.1)

    def test_bresil_humidite_trop_basse_alerte(self):
        """52.9% est juste sous la limite basse → alerte."""
        assert AlerteMetier.humidite_hors_seuil("Bresil", 52.9)

    def test_bresil_humidite_milieu_plage_ok(self):
        """55.5% est au milieu de la plage → pas d'alerte."""
        assert not AlerteMetier.humidite_hors_seuil("Bresil", 55.5)

    # ── Colombie (80% ±2 → plage [78, 82]) ─────────────────

    def test_colombie_humidite_ideale_ok(self):
        """80% est la valeur idéale Colombie → pas d'alerte."""
        assert not AlerteMetier.humidite_hors_seuil("Colombie", 80.0)

    def test_colombie_humidite_hors_seuil_alerte(self):
        """50% est très loin de 80% ±2 → alerte."""
        assert AlerteMetier.humidite_hors_seuil("Colombie", 50.0)

    # ── Valeurs extrêmes ────────────────────────────────────

    def test_humidite_zero_alerte(self):
        """0% → toujours une alerte (impossible physiquement en entrepôt)."""
        assert AlerteMetier.humidite_hors_seuil("Bresil", 0.0)

    def test_humidite_cent_alerte(self):
        """100% → toujours une alerte pour le Brésil (seuil max 57%)."""
        assert AlerteMetier.humidite_hors_seuil("Bresil", 100.0)

    # ── Pays inconnu ────────────────────────────────────────

    def test_pays_inconnu_leve_keyerror(self):
        """Un pays non configuré doit lever KeyError."""
        with pytest.raises(KeyError):
            AlerteMetier.humidite_hors_seuil("France", 60.0)


# ════════════════════════════════════════════════════════════
# TESTS — Péremption des lots
# ════════════════════════════════════════════════════════════

class TestPeremptionLots:
    """
    Vérifie la règle de péremption.

    RÈGLE CHOISIE : >= 365 jours → périmé (limite INCLUSE).
    → Supprime TestLogiqueLotsPerimes dans test_models_and_logic.py
      qui utilisait la logique inverse (< strictement).
    """

    def test_lot_stocke_hier_pas_perime(self):
        """Lot stocké il y a 1 jour → pas périmé."""
        date = datetime.utcnow() - timedelta(days=1)
        assert not AlerteMetier.lot_perime(date)

    def test_lot_il_y_a_364_jours_pas_perime(self):
        """364 jours → pas encore périmé (un jour avant la limite)."""
        date = datetime.utcnow() - timedelta(days=364)
        assert not AlerteMetier.lot_perime(date)

    def test_lot_exactement_365_jours_perime(self):
        """
        365 jours exactement → périmé.
        Règle métier : la limite est incluse (>=).
        """
        date = datetime.utcnow() - timedelta(days=365)
        assert AlerteMetier.lot_perime(date)

    def test_lot_il_y_a_400_jours_perime(self):
        """400 jours → clairement périmé."""
        date = datetime.utcnow() - timedelta(days=400)
        assert AlerteMetier.lot_perime(date)

    def test_lot_il_y_a_2_ans_perime(self):
        """730 jours (2 ans) → périmé."""
        date = datetime.utcnow() - timedelta(days=730)
        assert AlerteMetier.lot_perime(date)

    def test_lot_date_future_pas_perime(self):
        """Date dans le futur (saisie erronée) → pas périmé."""
        date = datetime.utcnow() + timedelta(days=10)
        assert not AlerteMetier.lot_perime(date)

    def test_lot_perime_limite_personnalisee_30_jours(self):
        """Avec limite_jours=30, un lot de 31 jours est périmé."""
        date = datetime.utcnow() - timedelta(days=31)
        assert AlerteMetier.lot_perime(date, limite_jours=30)

    def test_lot_non_perime_limite_personnalisee_30_jours(self):
        """Avec limite_jours=30, un lot de 20 jours n'est pas périmé."""
        date = datetime.utcnow() - timedelta(days=20)
        assert not AlerteMetier.lot_perime(date, limite_jours=30)


# ════════════════════════════════════════════════════════════
# TESTS — Tri FIFO
# ════════════════════════════════════════════════════════════

class TestTriFIFO:
    """
    Vérifie que trier_lots_fifo retourne les lots du plus ancien au plus récent.
    """

    def test_trois_lots_melanges_tries_correctement(self):
        """Trois lots dans le désordre → triés du plus ancien au plus récent."""
        lots = [
            {"lot_id": "LOT-C", "date_stockage": datetime(2024, 3, 1)},
            {"lot_id": "LOT-A", "date_stockage": datetime(2024, 1, 1)},
            {"lot_id": "LOT-B", "date_stockage": datetime(2024, 2, 1)},
        ]
        result = trier_lots_fifo(lots)
        assert [l["lot_id"] for l in result] == ["LOT-A", "LOT-B", "LOT-C"]

    def test_un_seul_lot_retourne_identique(self):
        """Un seul lot → retourné tel quel."""
        lots = [{"lot_id": "LOT-SEUL", "date_stockage": datetime(2024, 6, 1)}]
        result = trier_lots_fifo(lots)
        assert len(result) == 1
        assert result[0]["lot_id"] == "LOT-SEUL"

    def test_lots_deja_tries_restent_dans_ordre(self):
        """Des lots déjà triés ne sont pas perturbés."""
        lots = [
            {"lot_id": "LOT-1", "date_stockage": datetime(2023, 1, 1)},
            {"lot_id": "LOT-2", "date_stockage": datetime(2023, 6, 1)},
            {"lot_id": "LOT-3", "date_stockage": datetime(2024, 1, 1)},
        ]
        result = trier_lots_fifo(lots)
        assert [l["lot_id"] for l in result] == ["LOT-1", "LOT-2", "LOT-3"]

    def test_liste_vide_retourne_liste_vide(self):
        """Liste vide en entrée → liste vide en sortie."""
        assert trier_lots_fifo([]) == []

    def test_lots_meme_date_ordre_stable(self):
        """
        Deux lots avec la même date → le tri ne doit pas planter
        et les deux éléments doivent être présents.
        """
        lots = [
            {"lot_id": "LOT-X", "date_stockage": datetime(2024, 1, 1)},
            {"lot_id": "LOT-Y", "date_stockage": datetime(2024, 1, 1)},
        ]
        result = trier_lots_fifo(lots)
        assert len(result) == 2
        assert {l["lot_id"] for l in result} == {"LOT-X", "LOT-Y"}

    def test_tri_ne_modifie_pas_liste_originale(self):
        """trier_lots_fifo ne doit pas modifier la liste passée en argument."""
        lots = [
            {"lot_id": "LOT-C", "date_stockage": datetime(2024, 3, 1)},
            {"lot_id": "LOT-A", "date_stockage": datetime(2024, 1, 1)},
        ]
        original_order = [l["lot_id"] for l in lots]
        trier_lots_fifo(lots)
        assert [l["lot_id"] for l in lots] == original_order


# ════════════════════════════════════════════════════════════
# TESTS — Construction des messages d'alerte
# ════════════════════════════════════════════════════════════

class TestMessagesAlertes:
    """
    Vérifie que construire_message_alerte retourne un message
    lisible contenant les bonnes valeurs et le bon vocabulaire.
    """

    def test_message_temperature_contient_valeur(self):
        """Le message température doit contenir la valeur mesurée."""
        msg = construire_message_alerte("temperature", 35.0, 26.0, 32.0)
        assert "35.0" in msg

    def test_message_temperature_contient_mot_cle(self):
        """Le message température doit contenir le mot 'température'."""
        msg = construire_message_alerte("temperature", 35.0, 26.0, 32.0)
        assert "température" in msg.lower()

    def test_message_temperature_contient_seuils(self):
        """Le message température doit mentionner les deux seuils."""
        msg = construire_message_alerte("temperature", 35.0, 26.0, 32.0)
        assert "26.0" in msg
        assert "32.0" in msg

    def test_message_humidite_contient_valeur(self):
        """Le message humidité doit contenir la valeur mesurée."""
        msg = construire_message_alerte("humidite", 70.0, 53.0, 57.0)
        assert "70.0" in msg

    def test_message_humidite_contient_mot_cle(self):
        """Le message humidité doit contenir le mot 'humidité'."""
        msg = construire_message_alerte("humidite", 70.0, 53.0, 57.0)
        assert "humidité" in msg.lower()

    def test_message_humidite_contient_seuils(self):
        """Le message humidité doit mentionner les deux seuils."""
        msg = construire_message_alerte("humidite", 70.0, 53.0, 57.0)
        assert "53.0" in msg
        assert "57.0" in msg

    def test_message_type_inconnu_contient_valeur(self):
        """Un type inconnu → le message doit quand même contenir la valeur."""
        msg = construire_message_alerte("inconnu", 42.0, 0.0, 100.0)
        assert "42.0" in msg

    def test_message_retourne_chaine(self):
        """construire_message_alerte doit toujours retourner une str non vide."""
        for type_alerte in ["temperature", "humidite", "lot_perime", "inconnu"]:
            msg = construire_message_alerte(type_alerte, 30.0, 20.0, 40.0)
            assert isinstance(msg, str)
            assert len(msg) > 0

    def test_message_temperature_valeur_entiere(self):
        """La fonction doit accepter une valeur entière (int) sans erreur."""
        msg = construire_message_alerte("temperature", 35, 26.0, 32.0)
        assert "35" in msg
