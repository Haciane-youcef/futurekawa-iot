"""
FutureKawa — Tests Unitaires (modèles SQLAlchemy)
tests/unit/test_models_and_logic.py
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
from models import (
    Base, Config, Exploitation, Entrepot, Capteur, Mesure, Lot,
    AlerteMesure, AlerteLot, Utilisateur, Role,
    UtilisateurRole, UtilisateurExploitation, UtilisateurEntrepot
)


# ════════════════════════════════════════════════════════════
# FIXTURE PARTAGÉE
# ════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


# ════════════════════════════════════════════════════════════
# MODÈLE CONFIG
# ════════════════════════════════════════════════════════════

class TestConfigModel:

    def test_creation_complete(self, db_session):
        config = Config(
            pays="Bresil", temp_ideale=29.0, hum_ideale=55.0,
            tolerance_temp=3.0, tolerance_hum=2.0,
            email_destinataire="test@futurekawa.com",
            intervalle_verification=86400
        )
        db_session.add(config)
        db_session.commit()
        assert config.id_config is not None
        assert config.temp_ideale == 29.0

    def test_tolerance_zero_acceptee(self, db_session):
        config = Config(
            pays="TestZero", temp_ideale=25.0, hum_ideale=50.0,
            tolerance_temp=0.0, tolerance_hum=0.0,
            email_destinataire="a@b.com", intervalle_verification=3600
        )
        db_session.add(config)
        db_session.commit()
        assert config.tolerance_temp == 0.0

    def test_modification_email_persiste(self, db_session):
        config = Config(
            pays="ConfigMaj", temp_ideale=28.0, hum_ideale=54.0,
            tolerance_temp=2.0, tolerance_hum=1.0,
            email_destinataire="ancien@test.com", intervalle_verification=3600
        )
        db_session.add(config)
        db_session.commit()
        config.email_destinataire = "nouveau@test.com"
        db_session.commit()
        db_session.refresh(config)
        assert config.email_destinataire == "nouveau@test.com"


# ════════════════════════════════════════════════════════════
# MODÈLE EXPLOITATION
# ════════════════════════════════════════════════════════════

class TestExploitationModel:

    def test_creation(self, db_session):
        config = Config(
            pays="Bresil", temp_ideale=29.0, hum_ideale=55.0,
            tolerance_temp=3.0, tolerance_hum=2.0,
            email_destinataire="t@t.com", intervalle_verification=3600
        )
        db_session.add(config)
        db_session.commit()

        expl = Exploitation(nom="Fazenda Teste", id_config=config.id_config)
        db_session.add(expl)
        db_session.commit()
        assert expl.id_exploitation is not None
        assert expl.config.pays == "Bresil"


# ════════════════════════════════════════════════════════════
# MODÈLE ENTREPOT
# ════════════════════════════════════════════════════════════

class TestEntrepotModel:

    def test_creation(self, db_session):
        config = Config(
            pays="Bresil", temp_ideale=29.0, hum_ideale=55.0,
            tolerance_temp=3.0, tolerance_hum=2.0,
            email_destinataire="t@t.com", intervalle_verification=3600
        )
        db_session.add(config)
        db_session.commit()
        expl = Exploitation(nom="Expl Ent", id_config=config.id_config)
        db_session.add(expl)
        db_session.commit()

        ent = Entrepot(nom="Ent A", localisation="Sao Paulo", id_exploitation=expl.id_exploitation)
        db_session.add(ent)
        db_session.commit()
        assert ent.id_entrepot is not None
        assert ent.exploitation.nom == "Expl Ent"


# ════════════════════════════════════════════════════════════
# MODÈLE CAPTEUR
# ════════════════════════════════════════════════════════════

class TestCapteurModel:

    def test_creation_statut_defaut(self, db_session):
        config = Config(
            pays="Bresil", temp_ideale=29.0, hum_ideale=55.0,
            tolerance_temp=3.0, tolerance_hum=2.0,
            email_destinataire="t@t.com", intervalle_verification=3600
        )
        db_session.add(config)
        db_session.commit()
        expl = Exploitation(nom="Expl Cap", id_config=config.id_config)
        db_session.add(expl)
        db_session.commit()
        ent = Entrepot(nom="Ent Cap", localisation="Loc", id_exploitation=expl.id_exploitation)
        db_session.add(ent)
        db_session.commit()

        cap = Capteur(type_capteur="temperature", reference="CAP-001", id_entrepot=ent.id_entrepot)
        db_session.add(cap)
        db_session.commit()
        assert cap.statut == "actif"


# ════════════════════════════════════════════════════════════
# MODÈLE MESURE
# ════════════════════════════════════════════════════════════

class TestMesureModel:

    def test_insertion_valeurs_normales(self, db_session):
        # Créer la chaîne complète
        config = Config(
            pays="Bresil", temp_ideale=29.0, hum_ideale=55.0,
            tolerance_temp=3.0, tolerance_hum=2.0,
            email_destinataire="t@t.com", intervalle_verification=3600
        )
        db_session.add(config)
        db_session.commit()
        expl = Exploitation(nom="Expl Mes", id_config=config.id_config)
        db_session.add(expl)
        db_session.commit()
        ent = Entrepot(nom="Ent Mes", localisation="Loc", id_exploitation=expl.id_exploitation)
        db_session.add(ent)
        db_session.commit()
        cap = Capteur(type_capteur="temp", reference="CAP-MES", id_entrepot=ent.id_entrepot)
        db_session.add(cap)
        db_session.commit()

        m = Mesure(temperature=28.5, humidite=53.0, date_mesure=datetime.utcnow(), id_capteur=cap.id_capteur)
        db_session.add(m)
        db_session.commit()
        assert m.id_mesure is not None
        assert m.temperature == 28.5
        assert m.humidite == 53.0

    def test_temperature_negative_acceptee(self, db_session):
        # Utiliser le dernier capteur créé
        cap = db_session.query(Capteur).first()
        m = Mesure(temperature=-5.0, humidite=40.0, id_capteur=cap.id_capteur)
        db_session.add(m)
        db_session.commit()
        assert m.temperature == -5.0

    def test_date_mesure_optionnelle(self, db_session):
        cap = db_session.query(Capteur).first()
        m = Mesure(temperature=22.0, humidite=45.0, id_capteur=cap.id_capteur)
        db_session.add(m)
        db_session.commit()
        assert m.id_mesure is not None


# ════════════════════════════════════════════════════════════
# MODÈLE LOT
# ════════════════════════════════════════════════════════════

class TestLotModel:

    def test_creation_complete(self, db_session):
        config = Config(
            pays="Bresil", temp_ideale=29.0, hum_ideale=55.0,
            tolerance_temp=3.0, tolerance_hum=2.0,
            email_destinataire="t@t.com", intervalle_verification=3600
        )
        db_session.add(config)
        db_session.commit()
        expl = Exploitation(nom="Expl Lot", id_config=config.id_config)
        db_session.add(expl)
        db_session.commit()
        ent = Entrepot(nom="Ent Lot", localisation="Loc", id_exploitation=expl.id_exploitation)
        db_session.add(ent)
        db_session.commit()
        usr = Utilisateur(nom="Dupont", prenom="Jean", email="j@t.com", mot_de_passe="p")
        db_session.add(usr)
        db_session.commit()

        lot = Lot(id_lot="LOT-UNIT-001", id_entrepot=ent.id_entrepot, id_utilisateur=usr.id_utilisateur)
        db_session.add(lot)
        db_session.commit()
        assert lot.statut == "conforme"
        assert lot.date_stockage is not None

    def test_lot_id_unique_contrainte(self, db_session):
        lot1 = db_session.query(Lot).first()
        if lot1 is None:
            pytest.skip("Pas de lot de base")

        lot2 = Lot(id_lot="LOT-UNIT-001", id_entrepot=lot1.id_entrepot, id_utilisateur=lot1.id_utilisateur)
        db_session.add(lot2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_changement_statut_persiste(self, db_session):
        lot = db_session.query(Lot).first()
        lot.statut = "perime"
        db_session.commit()
        db_session.refresh(lot)
        assert lot.statut == "perime"


# ════════════════════════════════════════════════════════════
# MODÈLE ALERTE_MESURE
# ════════════════════════════════════════════════════════════

class TestAlerteMesureModel:

    def test_alerte_temperature_complete(self, db_session):
        mesure = db_session.query(Mesure).first()
        a = AlerteMesure(
            type_alerte="temperature",
            message="Temperature anormale : 35C",
            valeur_mesuree=35.0,
            seuil_min=26.0,
            seuil_max=32.0,
            statut="non_lue",
            id_mesure=mesure.id_mesure
        )
        db_session.add(a)
        db_session.commit()
        assert a.id_alerte_mesure is not None
        assert a.statut == "non_lue"

    def test_statut_defaut_non_lue(self, db_session):
        mesure = db_session.query(Mesure).first()
        a = AlerteMesure(
            type_alerte="humidite",
            message="Humidite anormale",
            valeur_mesuree=70.0,
            seuil_min=53.0,
            seuil_max=57.0,
            id_mesure=mesure.id_mesure
        )
        db_session.add(a)
        db_session.commit()
        assert a.statut == "non_lue"

    def test_marquer_alerte_lue(self, db_session):
        a = db_session.query(AlerteMesure).first()
        a.statut = "lue"
        db_session.commit()
        db_session.refresh(a)
        assert a.statut == "lue"


# ════════════════════════════════════════════════════════════
# MODÈLE ALERTE_LOT
# ════════════════════════════════════════════════════════════

class TestAlerteLotModel:

    def test_alerte_lot_perime(self, db_session):
        lot = db_session.query(Lot).first()
        a = AlerteLot(
            message=f"Lot {lot.id_lot} perime",
            id_lot=lot.id_lot
        )
        db_session.add(a)
        db_session.commit()
        assert a.id_alerte_lot is not None
        assert a.statut == "non_lue"


# ════════════════════════════════════════════════════════════
# MODÈLE UTILISATEUR
# ════════════════════════════════════════════════════════════

class TestUtilisateurModel:

    def test_creation_complete(self, db_session):
        usr = Utilisateur(nom="Martin", prenom="Alice", email="alice@test.com", mot_de_passe="pwd")
        db_session.add(usr)
        db_session.commit()
        assert usr.id_utilisateur is not None
        assert usr.actif is True

    def test_email_unique(self, db_session):
        usr2 = Utilisateur(nom="Dup", prenom="Licat", email="alice@test.com", mot_de_passe="pwd")
        db_session.add(usr2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


# ════════════════════════════════════════════════════════════
# MODÈLE ROLE
# ════════════════════════════════════════════════════════════

class TestRoleModel:

    def test_creation(self, db_session):
        role = Role(libelle="admin", description="Administrateur")
        db_session.add(role)
        db_session.commit()
        assert role.id_role is not None

    def test_libelle_unique(self, db_session):
        role2 = Role(libelle="admin")
        db_session.add(role2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


# ════════════════════════════════════════════════════════════
# MODÈLE UTILISATEUR_ROLE
# ════════════════════════════════════════════════════════════

class TestUtilisateurRoleModel:

    def test_association(self, db_session):
        usr = db_session.query(Utilisateur).first()
        role = db_session.query(Role).first()
        ur = UtilisateurRole(id_utilisateur=usr.id_utilisateur, id_role=role.id_role)
        db_session.add(ur)
        db_session.commit()
        assert ur.id_utilisateur_role is not None


# ════════════════════════════════════════════════════════════
# MODÈLE UTILISATEUR_EXPLOITATION
# ════════════════════════════════════════════════════════════

class TestUtilisateurExploitationModel:

    def test_association(self, db_session):
        usr = db_session.query(Utilisateur).first()
        expl = db_session.query(Exploitation).first()
        ue = UtilisateurExploitation(
            id_utilisateur=usr.id_utilisateur,
            id_exploitation=expl.id_exploitation
        )
        db_session.add(ue)
        db_session.commit()
        assert ue.id_utilisateur_exploitation is not None
        assert ue.date_fin is None


# ════════════════════════════════════════════════════════════
# MODÈLE UTILISATEUR_ENTREPOT
# ════════════════════════════════════════════════════════════

class TestUtilisateurEntrepotModel:

    def test_association(self, db_session):
        usr = db_session.query(Utilisateur).first()
        ent = db_session.query(Entrepot).first()
        ue = UtilisateurEntrepot(
            id_utilisateur=usr.id_utilisateur,
            id_entrepot=ent.id_entrepot
        )
        db_session.add(ue)
        db_session.commit()
        assert ue.id_utilisateur_entrepot is not None