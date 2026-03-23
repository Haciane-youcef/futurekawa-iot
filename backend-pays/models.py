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
    statut        = Column(String, default="conforme")  # conforme / alerte / perime
