import os
import json
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import paho.mqtt.client as mqtt
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from database import get_db, engine, SessionLocal
from models import Base, Mesure, Lot, Config

# =====================
# INITIALISATION
# =====================
app = FastAPI(title="FutureKawa - Backend Brésil")

Base.metadata.create_all(bind=engine)

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT   = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC  = "capteur/mesures"

# =====================
# CONFIG EMAIL
# =====================
SMTP_SERVER    = "smtp.gmail.com"
SMTP_PORT      = 587
SENDER_EMAIL   = " "    # ← remplace
SENDER_PASSWORD = " "  # ← mot de passe application Gmail

# =====================
# CACHE CONFIG
# =====================
config_cache = None

def get_config():
    global config_cache

    if config_cache is None:
        db = SessionLocal()
        try:
            config = db.query(Config).first()

            if config is None:
                print("Aucune config en BDD - utilisez POST /config")
                return None

            config_cache = {
                "pays"                   : config.pays,
                "temp_ideale"            : config.temp_ideale,
                "hum_ideale"             : config.hum_ideale,
                "tolerance_temp"         : config.tolerance_temp,
                "tolerance_hum"          : config.tolerance_hum,
                "email_destinataire"     : config.email_destinataire,
                "intervalle_verification": config.intervalle_verification
            }
            print(f"Config chargee depuis BDD : {config_cache}")

        finally:
            db.close()

    return config_cache

def vider_cache():
    global config_cache
    config_cache = None
    print("Cache reinitialise -> sera relu depuis BDD")

# =====================
# PYDANTIC MODELS
# =====================
class ConfigCreate(BaseModel):
    pays                    : str
    temp_ideale             : float
    hum_ideale              : float
    tolerance_temp          : float
    tolerance_hum           : float
    email_destinataire      : str
    intervalle_verification : int

class ConfigUpdate(BaseModel):
    pays                    : Optional[str]   = None
    temp_ideale             : Optional[float] = None
    hum_ideale              : Optional[float] = None
    tolerance_temp          : Optional[float] = None
    tolerance_hum           : Optional[float] = None
    email_destinataire      : Optional[str]   = None
    intervalle_verification : Optional[int]   = None

class LotCreate(BaseModel):
    lot_id      : str
    pays        : str
    exploitation: str
    entrepot    : str

# =====================
# ENVOI EMAIL
# =====================
def send_email(receiver_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From']    = SENDER_EMAIL
        msg['To']      = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        print("E-mail envoye avec succes !")
        server.quit()

    except Exception as e:
        print(f"Erreur envoi email : {e}")

# =====================
# VÉRIFICATION ALERTES MESURES
# =====================
def verifier_alertes_mesures(temperature, humidite):
    config = get_config()

    if config is None:
        print("Pas de config - alertes desactivees")
        return

    alertes = []

    if temperature < (config["temp_ideale"] - config["tolerance_temp"]) or \
       temperature > (config["temp_ideale"] + config["tolerance_temp"]):
        alertes.append(
            f"- Temperature: {temperature}C "
            f"(ideal: {config['temp_ideale']}C "
            f"+/- {config['tolerance_temp']}C)"
        )

    if humidite < (config["hum_ideale"] - config["tolerance_hum"]) or \
       humidite > (config["hum_ideale"] + config["tolerance_hum"]):
        alertes.append(
            f"- Humidite: {humidite}% "
            f"(ideal: {config['hum_ideale']}% "
            f"+/- {config['tolerance_hum']}%)"
        )

    if alertes:
        details = "\n".join(alertes)
        body = f"""
Bonjour 👋,

🔍 Une anomalie a été détectée dans les conditions de stockage.

📊 Détails de l'alerte :
{details}

Pays     : {config['pays']}
Date     : {datetime.utcnow()}

Veuillez consulter le tableau de bord pour plus de détails et prendre les mesures nécessaires.

Merci de votre vigilance ! ✅

Cordialement,
L'équipe FutureKawa 🤖
        """
        send_email(
            config["email_destinataire"],
            "🚨 Alerte : Anomalie détectée dans les conditions de stockage !",
            body
        )

# =====================
# VÉRIFICATION ALERTES LOTS
# =====================
def verifier_alertes_lots():
    config = get_config()

    if config is None:
        print("Pas de config - verification lots desactivee")
        return

    db = SessionLocal()
    try:
        limite       = datetime.utcnow() - timedelta(days=365)
        lots_anciens = db.query(Lot).filter(
            Lot.date_stockage < limite,
            Lot.statut != "perime"
        ).all()

        for lot in lots_anciens:
            lot.statut = "perime"
            db.commit()

            body = f"""
Bonjour 👋,

🔍 Un lot dépasse 365 jours de stockage.

📊 Détails du lot :
- Lot ID     : {lot.lot_id}
- Pays       : {lot.pays}
- Entrepot   : {lot.entrepot}
- Stocké le  : {lot.date_stockage}
- Date alerte: {datetime.utcnow()}

Veuillez consulter le tableau de bord pour plus de détails et prendre les mesures nécessaires.

Merci de votre vigilance ! ✅

Cordialement,
L'équipe FutureKawa 🤖
            """
            send_email(
                config["email_destinataire"],
                f"🚨 Alerte : Lot périmé {lot.lot_id} !",
                body
            )
            print(f"Alerte lot perime envoye : {lot.lot_id}")

    finally:
        db.close()

# =====================
# TACHE PERIODIQUE LOTS
# =====================
def tache_periodique():
    while True:
        print("Verification periodique des lots...")
        verifier_alertes_lots()

        config = get_config()
        if config is None:
            intervalle = 86400
        else:
            intervalle = config["intervalle_verification"]

        print(f"Prochaine verification dans {intervalle} secondes")
        time.sleep(intervalle)

# =====================
# MQTT
# =====================
def on_connect(client, userdata, flags, rc):
    print(f"MQTT connecte (code: {rc})")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    try:
        data        = json.loads(msg.payload.decode())
        temperature = data.get("temperature")
        humidite    = data.get("humidite")

        print(f"Mesure recue -> Temp: {temperature}C | Humidite: {humidite}%")

        db = SessionLocal()
        mesure = Mesure(
            temperature=temperature,
            humidite=humidite,
            date_mesure=datetime.utcnow()
        )
        db.add(mesure)
        db.commit()
        db.close()

        verifier_alertes_mesures(temperature, humidite)

    except Exception as e:
        print(f"Erreur MQTT : {e}")

def demarrer_mqtt():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()

threading.Thread(target=demarrer_mqtt,    daemon=True).start()
threading.Thread(target=tache_periodique, daemon=True).start()

# =====================
# API REST
# =====================

@app.get("/")
def accueil():
    return {"message": "FutureKawa Backend Brésil - API en ligne"}

# ── Mesures ──────────────────────────────────────────
@app.get("/mesures")
def get_mesures(db: Session = Depends(get_db)):
    return db.query(Mesure).order_by(Mesure.date_mesure.desc()).all()

@app.get("/mesures/dernieres/{n}")
def get_dernieres_mesures(n: int, db: Session = Depends(get_db)):
    return db.query(Mesure).order_by(Mesure.date_mesure.desc()).limit(n).all()

# ── Lots ─────────────────────────────────────────────
@app.post("/lots")
def creer_lot(lot: LotCreate, db: Session = Depends(get_db)):
    nouveau_lot = Lot(
        lot_id=lot.lot_id,
        pays=lot.pays,
        exploitation=lot.exploitation,
        entrepot=lot.entrepot,
        date_stockage=datetime.utcnow(),
        statut="conforme"
    )
    db.add(nouveau_lot)
    db.commit()
    db.refresh(nouveau_lot)
    return nouveau_lot

@app.get("/lots")
def get_lots(db: Session = Depends(get_db)):
    return db.query(Lot).order_by(Lot.date_stockage.asc()).all()

@app.get("/lots/alertes/liste")
def get_lots_alertes(db: Session = Depends(get_db)):
    return db.query(Lot).filter(Lot.statut != "conforme").all()

@app.get("/lots/{lot_id}")
def get_lot(lot_id: str, db: Session = Depends(get_db)):
    lot = db.query(Lot).filter(Lot.lot_id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot non trouve")
    return lot

@app.put("/lots/{lot_id}/statut")
def update_statut(lot_id: str, statut: str, db: Session = Depends(get_db)):
    lot = db.query(Lot).filter(Lot.lot_id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot non trouve")
    lot.statut = statut
    db.commit()
    db.refresh(lot)
    return lot

# ── Config ───────────────────────────────────────────
@app.post("/config")
def creer_config(config: ConfigCreate, db: Session = Depends(get_db)):
    existing = db.query(Config).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Config existe deja - utilisez PUT /config"
        )
    nouvelle_config = Config(
        pays=config.pays,
        temp_ideale=config.temp_ideale,
        hum_ideale=config.hum_ideale,
        tolerance_temp=config.tolerance_temp,
        tolerance_hum=config.tolerance_hum,
        email_destinataire=config.email_destinataire,
        intervalle_verification=config.intervalle_verification
    )
    db.add(nouvelle_config)
    db.commit()
    db.refresh(nouvelle_config)
    vider_cache()
    return nouvelle_config

@app.get("/config")
def get_config_api(db: Session = Depends(get_db)):
    config = db.query(Config).first()
    if not config:
        raise HTTPException(
            status_code=404,
            detail="Aucune config - utilisez POST /config"
        )
    return config

@app.put("/config")
def update_config(config: ConfigUpdate, db: Session = Depends(get_db)):
    existing = db.query(Config).first()
    if not existing:
        raise HTTPException(
            status_code=404,
            detail="Aucune config - utilisez POST /config"
        )

    if config.pays                    is not None: existing.pays                    = config.pays
    if config.temp_ideale             is not None: existing.temp_ideale             = config.temp_ideale
    if config.hum_ideale              is not None: existing.hum_ideale              = config.hum_ideale
    if config.tolerance_temp          is not None: existing.tolerance_temp          = config.tolerance_temp
    if config.tolerance_hum           is not None: existing.tolerance_hum           = config.tolerance_hum
    if config.email_destinataire      is not None: existing.email_destinataire      = config.email_destinataire
    if config.intervalle_verification is not None: existing.intervalle_verification = config.intervalle_verification

    db.commit()
    db.refresh(existing)
    vider_cache()

    return {"message": "Config mise a jour", "config": existing}