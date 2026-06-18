"""
FutureKawa — Modèles SQLAlchemy (MLD complète)
13 tables : CONFIG, EXPLOITATION, ENTREPOT, CAPTEUR, MESURE, LOT,
            ALERTE_MESURE, ALERTE_LOT, UTILISATEUR, ROLE,
            UTILISATEUR_ROLE, UTILISATEUR_EXPLOITATION, UTILISATEUR_ENTREPOT
"""
from sqlalchemy import (
    Column, Integer, Float, String, DateTime, Boolean, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


# ── CONFIG ───────────────────────────────────────────────────

class Config(Base):
    __tablename__ = "config"

    id_config               = Column(Integer, primary_key=True, autoincrement=True)
    pays                    = Column(String,  nullable=False)
    temp_ideale             = Column(Float,   nullable=False)
    hum_ideale              = Column(Float,   nullable=False)
    tolerance_temp          = Column(Float,   nullable=False)
    tolerance_hum           = Column(Float,   nullable=False)
    email_destinataire      = Column(String,  nullable=False)
    intervalle_verification = Column(Integer,  nullable=False)

    exploitations = relationship("Exploitation", back_populates="config")


# ── EXPLOITATION ─────────────────────────────────────────────

class Exploitation(Base):
    __tablename__ = "exploitation"

    id_exploitation = Column(Integer, primary_key=True, autoincrement=True)
    nom             = Column(String,  nullable=False)
    id_config       = Column(Integer, ForeignKey("config.id_config"), nullable=False)

    config                    = relationship("Config",       back_populates="exploitations")
    entrepots                 = relationship("Entrepot",     back_populates="exploitation")
    utilisateur_exploitations = relationship("UtilisateurExploitation", back_populates="exploitation")


# ── ENTREPOT ─────────────────────────────────────────────────

class Entrepot(Base):
    __tablename__ = "entrepot"

    id_entrepot     = Column(Integer, primary_key=True, autoincrement=True)
    nom             = Column(String,  nullable=False)
    localisation    = Column(String,  nullable=False)
    id_exploitation = Column(Integer, ForeignKey("exploitation.id_exploitation"), nullable=False)

    exploitation          = relationship("Exploitation",       back_populates="entrepots")
    capteurs              = relationship("Capteur",            back_populates="entrepot")
    lots                  = relationship("Lot",                back_populates="entrepot")
    utilisateur_entrepots = relationship("UtilisateurEntrepot", back_populates="entrepot")


# ── CAPTEUR ──────────────────────────────────────────────────

class Capteur(Base):
    __tablename__ = "capteur"

    id_capteur   = Column(Integer, primary_key=True, autoincrement=True)
    type_capteur = Column(String,  nullable=False)
    reference    = Column(String,  nullable=False)
    statut       = Column(String,  nullable=False, default="actif")
    id_entrepot  = Column(Integer, ForeignKey("entrepot.id_entrepot"), nullable=False)

    entrepot = relationship("Entrepot", back_populates="capteurs")
    mesures  = relationship("Mesure",   back_populates="capteur")


# ── MESURE ───────────────────────────────────────────────────

class Mesure(Base):
    __tablename__ = "mesure"

    id_mesure   = Column(Integer, primary_key=True, autoincrement=True)
    temperature = Column(Float,    nullable=False)
    humidite    = Column(Float,    nullable=False)
    date_mesure = Column(DateTime, default=datetime.utcnow, nullable=False)
    id_capteur  = Column(Integer,  ForeignKey("capteur.id_capteur"), nullable=False)

    capteur       = relationship("Capteur",       back_populates="mesures")
    alertes_mesure = relationship("AlerteMesure", back_populates="mesure")


# ── LOT ──────────────────────────────────────────────────────

class Lot(Base):
    __tablename__ = "lot"

    id_lot          = Column(String,    primary_key=True)
    date_stockage   = Column(DateTime,  default=datetime.utcnow, nullable=False)
    statut          = Column(String,    default="conforme", nullable=False)
    id_entrepot     = Column(Integer,   ForeignKey("entrepot.id_entrepot"), nullable=False)
    id_utilisateur  = Column(Integer,   ForeignKey("utilisateur.id_utilisateur"), nullable=False)

    entrepot    = relationship("Entrepot",    back_populates="lots")
    utilisateur = relationship("Utilisateur", back_populates="lots")
    alertes_lot = relationship("AlerteLot",   back_populates="lot")


# ── ALERTE_MESURE ────────────────────────────────────────────

class AlerteMesure(Base):
    __tablename__ = "alerte_mesure"

    id_alerte_mesure = Column(Integer,  primary_key=True, autoincrement=True)
    type_alerte      = Column(String,   nullable=False)
    message          = Column(String,   nullable=False)
    valeur_mesuree   = Column(Float,    nullable=False)
    seuil_min        = Column(Float,    nullable=False)
    seuil_max        = Column(Float,    nullable=False)
    date_alerte      = Column(DateTime, default=datetime.utcnow, nullable=False)
    statut           = Column(String,   default="non_lue", nullable=False)
    id_mesure        = Column(Integer,  ForeignKey("mesure.id_mesure"), nullable=False)

    mesure = relationship("Mesure", back_populates="alertes_mesure")


# ── ALERTE_LOT ───────────────────────────────────────────────

class AlerteLot(Base):
    __tablename__ = "alerte_lot"

    id_alerte_lot = Column(Integer,  primary_key=True, autoincrement=True)
    message       = Column(String,   nullable=False)
    date_alerte   = Column(DateTime, default=datetime.utcnow, nullable=False)
    statut        = Column(String,   default="non_lue", nullable=False)
    id_lot        = Column(String,   ForeignKey("lot.id_lot"), nullable=False)

    lot = relationship("Lot", back_populates="alertes_lot")


# ── UTILISATEUR ──────────────────────────────────────────────

class Utilisateur(Base):
    __tablename__ = "utilisateur"

    id_utilisateur = Column(Integer, primary_key=True, autoincrement=True)
    nom            = Column(String,  nullable=False)
    prenom         = Column(String,  nullable=False)
    email          = Column(String,  unique=True, nullable=False)
    mot_de_passe   = Column(String,  nullable=False)
    actif          = Column(Boolean, default=True, nullable=False)

    lots                        = relationship("Lot",                       back_populates="utilisateur")
    utilisateur_roles           = relationship("UtilisateurRole",           back_populates="utilisateur")
    utilisateur_exploitations   = relationship("UtilisateurExploitation",   back_populates="utilisateur")
    utilisateur_entrepots       = relationship("UtilisateurEntrepot",       back_populates="utilisateur")


# ── ROLE ─────────────────────────────────────────────────────

class Role(Base):
    __tablename__ = "role"

    id_role     = Column(Integer, primary_key=True, autoincrement=True)
    libelle     = Column(String,  unique=True, nullable=False)
    description = Column(String,  nullable=True)

    utilisateur_roles = relationship("UtilisateurRole", back_populates="role")


# ── UTILISATEUR_ROLE ─────────────────────────────────────────

class UtilisateurRole(Base):
    __tablename__ = "utilisateur_role"

    id_utilisateur_role = Column(Integer, primary_key=True, autoincrement=True)
    id_utilisateur      = Column(Integer, ForeignKey("utilisateur.id_utilisateur"), nullable=False)
    id_role             = Column(Integer, ForeignKey("role.id_role"), nullable=False)

    utilisateur = relationship("Utilisateur", back_populates="utilisateur_roles")
    role        = relationship("Role",        back_populates="utilisateur_roles")


# ── UTILISATEUR_EXPLOITATION ─────────────────────────────────

class UtilisateurExploitation(Base):
    __tablename__ = "utilisateur_exploitation"

    id_utilisateur_exploitation = Column(Integer,  primary_key=True, autoincrement=True)
    id_utilisateur              = Column(Integer,  ForeignKey("utilisateur.id_utilisateur"), nullable=False)
    id_exploitation             = Column(Integer,  ForeignKey("exploitation.id_exploitation"), nullable=False)
    date_debut                  = Column(DateTime, default=datetime.utcnow, nullable=False)
    date_fin                    = Column(DateTime, nullable=True)

    utilisateur   = relationship("Utilisateur",   back_populates="utilisateur_exploitations")
    exploitation  = relationship("Exploitation",  back_populates="utilisateur_exploitations")


# ── UTILISATEUR_ENTREPOT ─────────────────────────────────────

class UtilisateurEntrepot(Base):
    __tablename__ = "utilisateur_entrepot"

    id_utilisateur_entrepot = Column(Integer,  primary_key=True, autoincrement=True)
    id_utilisateur          = Column(Integer,  ForeignKey("utilisateur.id_utilisateur"), nullable=False)
    id_entrepot             = Column(Integer,  ForeignKey("entrepot.id_entrepot"), nullable=False)
    date_debut              = Column(DateTime, default=datetime.utcnow, nullable=False)
    date_fin                = Column(DateTime, nullable=True)

    utilisateur = relationship("Utilisateur", back_populates="utilisateur_entrepots")
    entrepot    = relationship("Entrepot",    back_populates="utilisateur_entrepots")