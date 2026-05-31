from sqlalchemy import Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

# Table des mesures IoT (température + humidité)
class Mesure(Base):
    __tablename__ = "mesures"

    id          = Column(Integer, primary_key=True, index=True)
    temperature = Column(Float, nullable=False)
    humidite    = Column(Float, nullable=False)
    date_mesure = Column(DateTime, default=datetime.utcnow)

# Table des lots de café
class Lot(Base):
    __tablename__ = "lots"

    id            = Column(Integer, primary_key=True, index=True)
    lot_id        = Column(String, unique=True, nullable=False)
    pays          = Column(String, nullable=False)
    exploitation  = Column(String, nullable=False)
    entrepot      = Column(String, nullable=False)
    date_stockage = Column(DateTime, default=datetime.utcnow)
    statut        = Column(String, default="conforme")

# Table de configuration (seuils + intervalle)
class Config(Base):
    __tablename__ = "config"

    id                      = Column(Integer, primary_key=True, index=True)
    pays                    = Column(String, nullable=False)
    temp_ideale             = Column(Float, nullable=False)
    hum_ideale              = Column(Float, nullable=False)
    tolerance_temp          = Column(Float, nullable=False)
    tolerance_hum           = Column(Float, nullable=False)
    email_destinataire      = Column(String, nullable=False)
    intervalle_verification = Column(Integer, nullable=False)  # en secondes


class Alerte(Base):
    __tablename__ = "alertes"

    id          = Column(Integer, primary_key=True, index=True)
    type_alerte = Column(String, nullable=False)  # "temperature", "humidite", "lot_perime"
    message     = Column(String, nullable=False)
    lot_id      = Column(String, nullable=True)   # seulement pour alertes lot
    valeur      = Column(Float, nullable=True)    # valeur mesurée
    seuil_min   = Column(Float, nullable=True)
    seuil_max   = Column(Float, nullable=True)
    date_alerte = Column(DateTime, default=datetime.utcnow)
    statut      = Column(String, default="non_lue")  # "non_lue" / "lue"    