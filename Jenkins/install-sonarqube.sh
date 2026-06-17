#!/bin/bash
# ============================================================
#  FutureKawa — Installation SonarQube en local (Docker)
#
#  Usage : bash install-sonarqube.sh
#
#  Ce script installe SonarQube Community Edition
#  sur ton poste local via Docker.
#
#  Prérequis :
#    - Docker Desktop lancé
#    - Au moins 4 Go de RAM disponibles (SonarQube est gourmand)
# ============================================================

set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   FutureKawa — Installation SonarQube local      ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Vérification Docker ───────────────────────────────────────
echo -e "${YELLOW}[0] Vérification Docker...${NC}"
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker non lancé.${NC}"; exit 1
fi
echo -e "${GREEN}✅ Docker OK${NC}"
echo ""

# ── Paramètre kernel requis par SonarQube (Elasticsearch) ────
# SonarQube utilise Elasticsearch en interne qui exige ce réglage
echo -e "${YELLOW}[1] Paramètre kernel vm.max_map_count...${NC}"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo sysctl -w vm.max_map_count=524288 2>/dev/null || true
    sudo sysctl -w fs.file-max=131072 2>/dev/null || true
    echo -e "${GREEN}✅ Paramètres kernel appliqués${NC}"
else
    echo "  macOS/Windows : paramètre géré automatiquement par Docker Desktop"
fi
echo ""

# ── Réseau partagé avec Jenkins ───────────────────────────────
echo -e "${YELLOW}[2] Réseau Docker partagé Jenkins + SonarQube...${NC}"
docker network create futurekawa-jenkins 2>/dev/null || echo "  Réseau existe déjà"
echo -e "${GREEN}✅ Réseau OK${NC}"
echo ""

# ── Volumes persistants SonarQube ────────────────────────────
echo -e "${YELLOW}[3] Création des volumes SonarQube...${NC}"
docker volume create sonarqube-data   2>/dev/null || true
docker volume create sonarqube-logs   2>/dev/null || true
docker volume create sonarqube-ext    2>/dev/null || true
docker volume create sonarqube-db     2>/dev/null || true
echo -e "${GREEN}✅ Volumes OK${NC}"
echo ""

# ── Base PostgreSQL dédiée SonarQube ────────────────────────
echo -e "${YELLOW}[4] Base de données PostgreSQL pour SonarQube...${NC}"
docker rm -f sonarqube-db 2>/dev/null || true

docker run -d \
    --name sonarqube-db \
    --restart unless-stopped \
    --network futurekawa-jenkins \
    -e POSTGRES_USER=sonar \
    -e POSTGRES_PASSWORD=sonar \
    -e POSTGRES_DB=sonarqube \
    -v sonarqube-db:/var/lib/postgresql/data \
    postgres:15

echo "  Attente PostgreSQL (10s)..."
sleep 10
echo -e "${GREEN}✅ PostgreSQL SonarQube démarré${NC}"
echo ""

# ── Conteneur SonarQube ───────────────────────────────────────
echo -e "${YELLOW}[5] Lancement SonarQube Community Edition...${NC}"
docker rm -f sonarqube 2>/dev/null || true

docker run -d \
    --name sonarqube \
    --restart unless-stopped \
    --network futurekawa-jenkins \
    -p 9000:9000 \
    -e SONAR_JDBC_URL=jdbc:postgresql://sonarqube-db:5432/sonarqube \
    -e SONAR_JDBC_USERNAME=sonar \
    -e SONAR_JDBC_PASSWORD=sonar \
    -v sonarqube-data:/opt/sonarqube/data \
    -v sonarqube-logs:/opt/sonarqube/logs \
    -v sonarqube-ext:/opt/sonarqube/extensions \
    sonarqube:community

echo ""
echo "  Attente du démarrage SonarQube (60-90s, premier lancement long)..."
MAX=36; COUNT=0
until curl -sf http://localhost:9000/api/system/status 2>/dev/null \
      | grep -q '"status":"UP"' || [ $COUNT -eq $MAX ]; do
    echo "  Démarrage en cours... ($((COUNT*5))s)"
    sleep 5
    COUNT=$((COUNT+1))
done

STATUS=$(curl -sf http://localhost:9000/api/system/status 2>/dev/null || echo '{}')
if echo "$STATUS" | grep -q '"status":"UP"'; then
    echo -e "${GREEN}✅ SonarQube est en ligne${NC}"
else
    echo -e "${YELLOW}⚠️  SonarQube démarre encore — attends 2 minutes et ouvre http://localhost:9000${NC}"
fi

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   SonarQube installé !                            ║${NC}"
echo -e "${BLUE}║                                                   ║${NC}"
echo -e "${BLUE}║   URL      : http://localhost:9000                ║${NC}"
echo -e "${BLUE}║   Login    : admin                                ║${NC}"
echo -e "${BLUE}║   Password : admin  (à changer au premier login)  ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "Prochaines étapes :"
echo "  1. Ouvre http://localhost:9000"
echo "  2. Connecte-toi avec admin/admin → change le mot de passe"
echo "  3. Crée un projet 'futurekawa-backend'"
echo "  4. Génère un token → copie-le dans Jenkins"
echo "  5. Crée un projet 'futurekawa-frontend'"
echo ""
