import os
import json
from sqlalchemy.exc import IntegrityError
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import paho.mqtt.client as mqtt
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from database import get_db, engine, SessionLocal
from models import Base, Mesure, Lot, Config, Alerte

# =====================
# INITIALISATION
# =====================

# Le pays est injecté par variable d'environnement — aucune valeur pays dans le code
PAYS = os.getenv("PAYS", "inconnu")

app = FastAPI(title=f"FutureKawa - Backend {PAYS.capitalize()}")

Base.metadata.create_all(bind=engine)

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT   = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC  = "capteur/mesures"

# =====================
# CONFIG EMAIL — 100% depuis variables d'environnement
# Ne jamais mettre de credentials dans le code source
# =====================
SMTP_SERVER     = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL    = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

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
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("SENDER_EMAIL ou SENDER_PASSWORD non definis — email non envoye")
        return

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

    db = SessionLocal()
    try:
        alertes_email = []

        # Vérif température
        if temperature < (config["temp_ideale"] - config["tolerance_temp"]) or \
           temperature > (config["temp_ideale"] + config["tolerance_temp"]):

            alerte = Alerte(
                type_alerte = "temperature",
                message     = (
                    f"Temperature anormale : {temperature}C "
                    f"(ideal: {config['temp_ideale']}C "
                    f"+/- {config['tolerance_temp']}C)"
                ),
                valeur      = temperature,
                seuil_min   = config["temp_ideale"] - config["tolerance_temp"],
                seuil_max   = config["temp_ideale"] + config["tolerance_temp"],
                date_alerte = datetime.utcnow(),
                statut      = "non_lue"
            )
            db.add(alerte)
            db.commit()
            print("Alerte temperature sauvegardee en BDD")

            alertes_email.append(
                f"- Temperature: {temperature}C "
                f"(ideal: {config['temp_ideale']}C "
                f"+/- {config['tolerance_temp']}C)"
            )

        # Vérif humidité
        if humidite < (config["hum_ideale"] - config["tolerance_hum"]) or \
           humidite > (config["hum_ideale"] + config["tolerance_hum"]):

            alerte = Alerte(
                type_alerte = "humidite",
                message     = (
                    f"Humidite anormale : {humidite}% "
                    f"(ideal: {config['hum_ideale']}% "
                    f"+/- {config['tolerance_hum']}%)"
                ),
                valeur      = humidite,
                seuil_min   = config["hum_ideale"] - config["tolerance_hum"],
                seuil_max   = config["hum_ideale"] + config["tolerance_hum"],
                date_alerte = datetime.utcnow(),
                statut      = "non_lue"
            )
            db.add(alerte)
            db.commit()
            print("Alerte humidite sauvegardee en BDD")

            alertes_email.append(
                f"- Humidite: {humidite}% "
                f"(ideal: {config['hum_ideale']}% "
                f"+/- {config['tolerance_hum']}%)"
            )

        # Envoi email si alertes
        if alertes_email:
            details = "\n".join(alertes_email)
            body = f"""Bonjour,

Une anomalie a ete detectee dans les conditions de stockage.

Details de l'alerte :
{details}

Pays : {config['pays']}
Date : {datetime.utcnow()}

Veuillez consulter le tableau de bord pour plus de details.

Cordialement,
L'equipe FutureKawa
"""
            send_email(
                config["email_destinataire"],
                "ALERTE : Anomalie detectee dans les conditions de stockage !",
                body
            )

    finally:
        db.close()


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

            alerte = Alerte(
                type_alerte = "lot_perime",
                message     = (
                    f"Lot {lot.lot_id} perime — stocke depuis "
                    f"{lot.date_stockage.strftime('%Y-%m-%d')}"
                ),
                lot_id      = lot.lot_id,
                date_alerte = datetime.utcnow(),
                statut      = "non_lue"
            )
            db.add(alerte)

        if lots_anciens:
            db.commit()
            ids = [lot.lot_id for lot in lots_anciens]
            print(f"{len(ids)} lot(s) marques perimes : {ids}")

            body = f"""Bonjour,

Les lots suivants ont depasse la duree maximale de stockage (365 jours) :

{chr(10).join('- ' + lot.lot_id for lot in lots_anciens)}

Pays : {config['pays']}
Date : {datetime.utcnow()}

Veuillez prendre les mesures necessaires.

Cordialement,
L'equipe FutureKawa
"""
            send_email(
                config["email_destinataire"],
                "ALERTE : Lots perimes detectes !",
                body
            )

    finally:
        db.close()


# =====================
# MQTT — RECEPTION MESURES
# =====================
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        temperature = payload.get("temperature")
        humidite    = payload.get("humidite")

        if temperature is None or humidite is None:
            print(f"Payload MQTT invalide : {payload}")
            return

        db = SessionLocal()
        try:
            mesure = Mesure(
                temperature = temperature,
                humidite    = humidite,
                date_mesure = datetime.utcnow()
            )
            db.add(mesure)
            db.commit()
            print(f"Mesure MQTT sauvegardee : temp={temperature} hum={humidite}")
        finally:
            db.close()

        verifier_alertes_mesures(temperature, humidite)

    except Exception as e:
        print(f"Erreur traitement message MQTT : {e}")


def demarrer_mqtt():
    while True:
        try:
            client = mqtt.Client()
            client.on_message = on_message
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.subscribe(MQTT_TOPIC)
            print(f"MQTT connecte sur {MQTT_BROKER}:{MQTT_PORT} — topic: {MQTT_TOPIC}")
            client.loop_forever()
        except Exception as e:
            print(f"MQTT echec connexion : {e} - retry dans 5s")
            time.sleep(5)


# =====================
# TÂCHE PÉRIODIQUE — VÉRIFICATION LOTS
# =====================
def tache_periodique():
    while True:
        config = get_config()
        intervalle = config["intervalle_verification"] if config else 3600
        time.sleep(intervalle)
        print("Tache periodique : verification des lots...")
        verifier_alertes_lots()


threading.Thread(target=demarrer_mqtt,    daemon=True).start()
threading.Thread(target=tache_periodique, daemon=True).start()

# =====================
# API REST
# =====================

@app.get("/")
def accueil():
    return {
        "message": f"FutureKawa Backend {PAYS.capitalize()} - API en ligne",
        "pays"   : PAYS
    }


# ── Mesures ──────────────────────────────────────────
@app.get("/mesures")
def get_mesures(db: Session = Depends(get_db)):
    return db.query(Mesure).order_by(Mesure.date_mesure.desc()).all()


@app.post("/mesures", status_code=status.HTTP_201_CREATED)
def creer_mesure(mesure_data: dict, db: Session = Depends(get_db)):
    if "temperature" not in mesure_data or mesure_data["temperature"] is None:
        raise HTTPException(status_code=422, detail="Field 'temperature' is required")

    nouvelle_mesure = Mesure(
        temperature = mesure_data["temperature"],
        humidite    = mesure_data.get("humidite"),
        date_mesure = datetime.utcnow()
    )
    db.add(nouvelle_mesure)
    db.commit()
    db.refresh(nouvelle_mesure)

    verifier_alertes_mesures(nouvelle_mesure.temperature, nouvelle_mesure.humidite)

    return nouvelle_mesure


@app.get("/mesures/dernieres/{n}")
def get_dernieres_mesures(n: int, db: Session = Depends(get_db)):
    return db.query(Mesure).order_by(Mesure.date_mesure.desc()).limit(n).all()


# ── Lots ─────────────────────────────────────────────
@app.post("/lots", status_code=status.HTTP_201_CREATED)
def creer_lot(lot: LotCreate, db: Session = Depends(get_db)):
    nouveau_lot = Lot(
        lot_id       = lot.lot_id,
        pays         = lot.pays,
        exploitation = lot.exploitation,
        entrepot     = lot.entrepot,
        date_stockage = datetime.utcnow(),
        statut       = "conforme"
    )
    db.add(nouveau_lot)
    try:
        db.commit()
        db.refresh(nouveau_lot)
        return nouveau_lot
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Un lot avec cet identifiant existe deja.")


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
        raise HTTPException(status_code=400, detail="Config existe deja - utilisez PUT /config")

    nouvelle_config = Config(
        pays                    = config.pays,
        temp_ideale             = config.temp_ideale,
        hum_ideale              = config.hum_ideale,
        tolerance_temp          = config.tolerance_temp,
        tolerance_hum           = config.tolerance_hum,
        email_destinataire      = config.email_destinataire,
        intervalle_verification = config.intervalle_verification
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
        raise HTTPException(status_code=404, detail="Aucune config - utilisez POST /config")
    return config


@app.put("/config")
def update_config(config: ConfigUpdate, db: Session = Depends(get_db)):
    existing = db.query(Config).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Aucune config - utilisez POST /config")

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


# ── Alertes ──────────────────────────────────────────
@app.get("/alertes")
def get_alertes(db: Session = Depends(get_db)):
    return db.query(Alerte).order_by(Alerte.date_alerte.desc()).all()


@app.post("/alertes", status_code=status.HTTP_201_CREATED)
def creer_alerte(alerte_data: dict, db: Session = Depends(get_db)):
    nouvelle_alerte = Alerte(
        type_alerte = alerte_data.get("type_alerte"),
        message     = alerte_data.get("message"),
        valeur      = alerte_data.get("valeur"),
        seuil_min   = alerte_data.get("seuil_min"),
        seuil_max   = alerte_data.get("seuil_max"),
        lot_id      = alerte_data.get("lot_id"),
        date_alerte = datetime.utcnow(),
        statut      = "non_lue"
    )
    db.add(nouvelle_alerte)
    db.commit()
    db.refresh(nouvelle_alerte)
    return nouvelle_alerte


@app.patch("/alertes/{alerte_id}")
def update_alerte(alerte_id: int, update_data: dict, db: Session = Depends(get_db)):
    alerte = db.query(Alerte).filter(Alerte.id == alerte_id).first()
    if not alerte:
        raise HTTPException(status_code=404, detail="Alerte non trouvee")

    if "statut" in update_data:
        alerte.statut = update_data["statut"]

    db.commit()
    db.refresh(alerte)
    return alerte


@app.get("/alertes/non-lues")
def get_alertes_non_lues(db: Session = Depends(get_db)):
    return db.query(Alerte).filter(
        Alerte.statut == "non_lue"
    ).order_by(Alerte.date_alerte.desc()).all()


@app.get("/alertes/count")
def get_alertes_count(db: Session = Depends(get_db)):
    total    = db.query(Alerte).count()
    non_lues = db.query(Alerte).filter(Alerte.statut == "non_lue").count()
    return {"total": total, "non_lues": non_lues}


@app.put("/alertes/{alerte_id}/lue")
def marquer_alerte_lue(alerte_id: int, db: Session = Depends(get_db)):
    alerte = db.query(Alerte).filter(Alerte.id == alerte_id).first()
    if not alerte:
        raise HTTPException(status_code=404, detail="Alerte non trouvee")
    alerte.statut = "lue"
    db.commit()
    db.refresh(alerte)
    return alerte


@app.put("/alertes/toutes/lues")
def marquer_toutes_lues(db: Session = Depends(get_db)):
    db.query(Alerte).filter(
        Alerte.statut == "non_lue"
    ).update({"statut": "lue"})
    db.commit()
    return {"message": "Toutes les alertes marquees comme lues"}


@app.delete("/alertes/{alerte_id}")
def supprimer_alerte(alerte_id: int, db: Session = Depends(get_db)):
    alerte = db.query(Alerte).filter(Alerte.id == alerte_id).first()
    if not alerte:
        raise HTTPException(status_code=404, detail="Alerte non trouvee")
    db.delete(alerte)
    db.commit()
    return {"message": "Alerte supprimee"}


@app.delete("/alertes")
def supprimer_toutes_alertes(db: Session = Depends(get_db)):
    db.query(Alerte).delete()
    db.commit()
    return {"message": "Toutes les alertes supprimees"}