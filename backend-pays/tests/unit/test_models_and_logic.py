"""
FutureKawa — Tests Unitaires (modèles SQLAlchemy)
tests/unit/test_models_and_logic.py

Ce fichier teste UNIQUEMENT la couche BDD (modèles, persistance, contraintes).
La logique métier pure (seuils, péremption, FIFO, messages) est testée dans
test_unit_alertes.py — les anciennes classes TestLogiqueSeuils et
TestLogiqueLotsPerimes ont été supprimées ici pour éviter les doublons.
"""

import os
import sys
import pytest
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "sqlite:///./futurekawa_test.db")
os.environ.setdefault("MQTT_BROKER",  "localhost")
os.environ.setdefault("MQTT_PORT",    "1883")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from models import Mesure, Lot, Config, Alerte, Base


# ════════════════════════════════════════════════════════════
# FIXTURE PARTAGÉE
# ════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def db_session():
    """Session SQLite en mémoire — isolée, rapide, sans fichier."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


# ════════════════════════════════════════════════════════════
# MODÈLE MESURE
# ════════════════════════════════════════════════════════════

class TestMesureModel:
    """Persistance et contraintes du modèle Mesure."""

    def test_insertion_valeurs_normales(self, db_session):
        """Mesure standard avec temp + humidité → persist OK, id attribué."""
        m = Mesure(temperature=28.5, humidite=53.0, date_mesure=datetime.utcnow())
        db_session.add(m)
        db_session.commit()
        assert m.id is not None
        assert m.temperature == 28.5
        assert m.humidite == 53.0

    def test_temperature_negative_acceptee(self, db_session):
        """SQLite accepte les températures négatives (pas de contrainte CHECK)."""
        m = Mesure(temperature=-5.0, humidite=40.0)
        db_session.add(m)
        db_session.commit()
        assert m.temperature == -5.0

    def test_humidite_100_acceptee(self, db_session):
        """100% d'humidité est une valeur limite valide en base."""
        m = Mesure(temperature=25.0, humidite=100.0)
        db_session.add(m)
        db_session.commit()
        assert m.humidite == 100.0

    def test_humidite_zero_acceptee(self, db_session):
        """0% d'humidité est persisté sans erreur."""
        m = Mesure(temperature=20.0, humidite=0.0)
        db_session.add(m)
        db_session.commit()
        assert m.humidite == 0.0

    def test_date_mesure_optionnelle(self, db_session):
        """Sans date_mesure explicite, l'objet est quand même persisté."""
        m = Mesure(temperature=22.0, humidite=45.0)
        db_session.add(m)
        db_session.commit()
        assert m.id is not None

    def test_lecture_mesure_par_id(self, db_session):
        """Une mesure insérée est récupérable par son id."""
        m = Mesure(temperature=30.0, humidite=60.0)
        db_session.add(m)
        db_session.commit()
        found = db_session.get(Mesure, m.id)
        assert found is not None
        assert found.temperature == 30.0


# ════════════════════════════════════════════════════════════
# MODÈLE LOT
# ════════════════════════════════════════════════════════════

class TestLotModel:
    """Persistance et contraintes du modèle Lot."""

    def test_creation_complete(self, db_session):
        """Lot avec tous les champs → persist OK."""
        lot = Lot(
            lot_id="LOT-UNIT-001",
            pays="Bresil",
            exploitation="Test Farm",
            entrepot="Entrepot A",
            statut="conforme"
        )
        db_session.add(lot)
        db_session.commit()
        assert lot.id is not None
        assert lot.statut == "conforme"

    def test_statut_defaut_conforme(self, db_session):
        """Sans statut explicite, le défaut est 'conforme'."""
        lot = Lot(
            lot_id="LOT-UNIT-002",
            pays="Ethiopie",
            exploitation="Farm Yirgacheffe",
            entrepot="Entrepot B"
        )
        db_session.add(lot)
        db_session.commit()
        assert lot.statut == "conforme"

    def test_lot_id_unique_contrainte(self, db_session):
        """Deux lots avec le même lot_id → IntegrityError."""
        lot1 = Lot(lot_id="LOT-DUPLICATE", pays="Bresil",
                   exploitation="Farm X", entrepot="Entrepot X")
        db_session.add(lot1)
        db_session.commit()

        lot2 = Lot(lot_id="LOT-DUPLICATE", pays="Colombia",
                   exploitation="Farm Y", entrepot="Entrepot Y")
        db_session.add(lot2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_changement_statut_persiste(self, db_session):
        """Modifier le statut d'un lot → changement visible après refresh."""
        lot = Lot(lot_id="LOT-STATUT-TEST", pays="Colombia",
                  exploitation="Farm Z", entrepot="Entrepot Z", statut="conforme")
        db_session.add(lot)
        db_session.commit()

        lot.statut = "perime"
        db_session.commit()
        db_session.refresh(lot)
        assert lot.statut == "perime"

    def test_tous_statuts_valides_acceptes(self, db_session):
        """Les trois statuts métier sont acceptés par SQLite."""
        for idx, statut in enumerate(["conforme", "en_alerte", "perime"]):
            lot = Lot(
                lot_id=f"LOT-STATUT-{idx}",
                pays="Bresil",
                exploitation="Farm",
                entrepot="Ent",
                statut=statut
            )
            db_session.add(lot)
            db_session.commit()
            assert lot.statut == statut

    def test_lecture_lot_par_lot_id(self, db_session):
        """Un lot inséré est retrouvable par filtre sur lot_id."""
        lot = Lot(lot_id="LOT-READ-TEST", pays="Bresil",
                  exploitation="Farm R", entrepot="Ent R")
        db_session.add(lot)
        db_session.commit()

        found = db_session.query(Lot).filter_by(lot_id="LOT-READ-TEST").first()
        assert found is not None
        assert found.pays == "Bresil"


# ════════════════════════════════════════════════════════════
# MODÈLE CONFIG
# ════════════════════════════════════════════════════════════

class TestConfigModel:
    """Persistance et contraintes du modèle Config."""

    def test_creation_complete(self, db_session):
        """Config avec tous les champs → persist OK."""
        config = Config(
            pays="Bresil",
            temp_ideale=29.0,
            hum_ideale=55.0,
            tolerance_temp=3.0,
            tolerance_hum=2.0,
            email_destinataire="test@futurekawa.com",
            intervalle_verification=86400
        )
        db_session.add(config)
        db_session.commit()
        assert config.id is not None
        assert config.temp_ideale == 29.0

    def test_tolerance_zero_acceptee(self, db_session):
        """Tolérance à 0 est une valeur valide en base."""
        config = Config(
            pays="TestZero",
            temp_ideale=25.0,
            hum_ideale=50.0,
            tolerance_temp=0.0,
            tolerance_hum=0.0,
            email_destinataire="a@b.com",
            intervalle_verification=3600
        )
        db_session.add(config)
        db_session.commit()
        assert config.tolerance_temp == 0.0
        assert config.tolerance_hum == 0.0

    def test_modification_email_persiste(self, db_session):
        """Modifier l'email d'une config → changement visible après refresh."""
        config = Config(
            pays="ConfigMaj",
            temp_ideale=28.0,
            hum_ideale=54.0,
            tolerance_temp=2.0,
            tolerance_hum=1.0,
            email_destinataire="ancien@test.com",
            intervalle_verification=3600
        )
        db_session.add(config)
        db_session.commit()

        config.email_destinataire = "nouveau@test.com"
        db_session.commit()
        db_session.refresh(config)
        assert config.email_destinataire == "nouveau@test.com"

    def test_intervalle_verification_long(self, db_session):
        """Un intervalle de 7 jours (604800s) est accepté."""
        config = Config(
            pays="TestIntervalle",
            temp_ideale=27.0,
            hum_ideale=52.0,
            tolerance_temp=3.0,
            tolerance_hum=2.0,
            email_destinataire="x@x.com",
            intervalle_verification=604800
        )
        db_session.add(config)
        db_session.commit()
        assert config.intervalle_verification == 604800


# ════════════════════════════════════════════════════════════
# MODÈLE ALERTE
# ════════════════════════════════════════════════════════════

class TestAlerteModel:
    """Persistance et contraintes du modèle Alerte."""

    def test_alerte_temperature_complete(self, db_session):
        """Alerte température avec tous les champs → persist OK."""
        a = Alerte(
            type_alerte="temperature",
            message="Température anormale : 35°C",
            valeur=35.0,
            seuil_min=26.0,
            seuil_max=32.0,
            statut="non_lue"
        )
        db_session.add(a)
        db_session.commit()
        assert a.id is not None
        assert a.type_alerte == "temperature"
        assert a.statut == "non_lue"

    def test_statut_defaut_non_lue(self, db_session):
        """Sans statut explicite, le défaut est 'non_lue'."""
        a = Alerte(type_alerte="humidite", message="Humidité anormale")
        db_session.add(a)
        db_session.commit()
        assert a.statut == "non_lue"

    def test_alerte_lot_perime_avec_lot_id(self, db_session):
        """Alerte de type lot_perime → lot_id correctement persisté."""
        a = Alerte(
            type_alerte="lot_perime",
            message="Lot LOT-ANCIEN-001 périmé",
            lot_id="LOT-ANCIEN-001"
        )
        db_session.add(a)
        db_session.commit()
        assert a.lot_id == "LOT-ANCIEN-001"

    def test_marquer_alerte_lue(self, db_session):
        """Changer le statut 'non_lue' → 'lue' → visible après refresh."""
        a = Alerte(type_alerte="temperature", message="Test lue", statut="non_lue")
        db_session.add(a)
        db_session.commit()

        a.statut = "lue"
        db_session.commit()
        db_session.refresh(a)
        assert a.statut == "lue"

    def test_alerte_sans_valeur_numerique(self, db_session):
        """Une alerte peut être créée sans valeur ni seuils (cas lot_perime)."""
        a = Alerte(
            type_alerte="lot_perime",
            message="Lot expiré",
            lot_id="LOT-EXP-001"
        )
        db_session.add(a)
        db_session.commit()
        assert a.id is not None
        assert a.valeur is None

    def test_plusieurs_alertes_independantes(self, db_session):
        """Plusieurs alertes peuvent coexister en base sans conflit."""
        alertes = [
            Alerte(type_alerte="temperature", message=f"Alerte {i}", statut="non_lue")
            for i in range(3)
        ]
        for a in alertes:
            db_session.add(a)
        db_session.commit()

        for a in alertes:
            assert a.id is not None

        # Tous les ids sont distincts
        ids = [a.id for a in alertes]
        assert len(set(ids)) == 3
