import os
import json
import threading
import paho.mqtt.client as mqtt
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db, engine, SessionLocal
from models import Base, Mesure, Lot

# =====================
# INITIALISATION
# =====================
app = FastAPI(title="FutureKawa - Backend Pays")

# Création des tables au démarrage
Base.metadata.create_all(bind=engine)

# Config MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT   = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC  = "capteur/mesures"

# =====================
# MQTT - Réception des données
# =====================
def on_connect(client, userdata, flags, rc):
    print(f"MQTT connecte au broker (code: {rc})")
    client.subscribe(MQTT_TOPIC)
    print(f"Abonne au topic : {MQTT_TOPIC}")

def on_message(client, userdata, msg):
    try:
        # Décodage du JSON
        data = json.loads(msg.payload.decode())
        temperature = data.get("temperature")
        humidite    = data.get("humidite")

        print(f"Mesure recue -> Temp: {temperature}°C | Humidite: {humidite}%")

        # Sauvegarde en base de données
        db = SessionLocal()
        mesure = Mesure(
            temperature=temperature,
            humidite=humidite,
            date_mesure=datetime.utcnow()
        )
        db.add(mesure)
        db.commit()
        db.close()

        print("Mesure sauvegardee en base !")

    except Exception as e:
        print(f"Erreur traitement message MQTT : {e}")

def demarrer_mqtt():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()

# Lancement MQTT dans un thread séparé
thread_mqtt = threading.Thread(target=demarrer_mqtt, daemon=True)
thread_mqtt.start()

# =====================
# API REST - Routes
# =====================

@app.get("/")
def accueil():
    return {"message": "FutureKawa Backend - API en ligne"}

# Récupérer toutes les mesures
@app.get("/mesures")
def get_mesures(db: Session = Depends(get_db)):
    mesures = db.query(Mesure).order_by(Mesure.date_mesure.desc()).all()
    return mesures

# Récupérer les N dernières mesures
@app.get("/mesures/dernieres/{n}")
def get_dernieres_mesures(n: int, db: Session = Depends(get_db)):
    mesures = db.query(Mesure).order_by(Mesure.date_mesure.desc()).limit(n).all()
    return mesures

# Créer un nouveau lot
@app.post("/lots")
def creer_lot(lot_id: str, pays: str, exploitation: str, entrepot: str, db: Session = Depends(get_db)):
    lot = Lot(
        lot_id=lot_id,
        pays=pays,
        exploitation=exploitation,
        entrepot=entrepot,
        date_stockage=datetime.utcnow(),
        statut="conforme"
    )
    db.add(lot)
    db.commit()
    db.refresh(lot)
    return lot

# Récupérer tous les lots triés par date (FIFO)
@app.get("/lots")
def get_lots(db: Session = Depends(get_db)):
    lots = db.query(Lot).order_by(Lot.date_stockage.asc()).all()
    return lots

# Récupérer un lot par ID
@app.get("/lots/{lot_id}")
def get_lot(lot_id: str, db: Session = Depends(get_db)):
    lot = db.query(Lot).filter(Lot.lot_id == lot_id).first()
    return lot
