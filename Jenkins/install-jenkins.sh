#!/bin/bash
# ============================================================
#  FutureKawa — Installation Jenkins en local (Docker)
#
#  Ce script installe Jenkins dans un conteneur Docker sur
#  ta machine locale. Jenkins pourra ensuite lancer le pipeline
#  FutureKawa automatiquement à chaque git push.
#
#  Usage : bash install-jenkins.sh
#
#  Prérequis : Docker Desktop lancé
# ============================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   FutureKawa — Installation Jenkins locale       ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Vérification Docker ───────────────────────────────────────
echo -e "${YELLOW}[0] Vérification de Docker...${NC}"
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker n'est pas lancé. Lance Docker Desktop d'abord.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker est disponible${NC}"
echo ""

# ── Création du réseau partagé ────────────────────────────────
echo -e "${YELLOW}[1] Création du réseau Docker partagé...${NC}"
docker network create futurekawa-jenkins 2>/dev/null || echo "  Réseau existe déjà"
echo -e "${GREEN}✅ Réseau futurekawa-jenkins OK${NC}"
echo ""

# ── Création du volume persistant Jenkins ─────────────────────
echo -e "${YELLOW}[2] Création du volume Jenkins...${NC}"
docker volume create jenkins-data 2>/dev/null || echo "  Volume existe déjà"
echo -e "${GREEN}✅ Volume jenkins-data OK${NC}"
echo ""

# ── Construction image Jenkins + docker-cli ───────────────────
echo -e "${YELLOW}[3] Construction de l'image Jenkins avec docker-cli...${NC}"

# Crée un Dockerfile temporaire
TMPDIR_BUILD=$(mktemp -d)
cat > "${TMPDIR_BUILD}/Dockerfile" <<'DOCKERFILE'
FROM jenkins/jenkins:lts-jdk17

USER root

# Installer docker-cli (sans le daemon)
RUN apt-get update && \
    apt-get install -y ca-certificates curl gnupg lsb-release && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    chmod a+r /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/debian \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
      > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y docker-ce-cli && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Ajouter jenkins au groupe docker
RUN groupadd -f docker && usermod -aG docker jenkins

USER jenkins
DOCKERFILE

docker build -t jenkins-futurekawa:local "${TMPDIR_BUILD}"
rm -rf "${TMPDIR_BUILD}"

echo -e "${GREEN}✅ Image jenkins-futurekawa:local construite${NC}"
echo ""

# ── Lancement du conteneur Jenkins ───────────────────────────
echo -e "${YELLOW}[4] Lancement du conteneur Jenkins...${NC}"

# Supprime l'ancienne instance si elle existe
docker rm -f jenkins-futurekawa 2>/dev/null || true

docker run -d \
    --name jenkins-futurekawa \
    --restart unless-stopped \
    -p 8081:8080 \
    -p 50000:50000 \
    -v jenkins-data:/var/jenkins_home \
    -v /var/run/docker.sock:/var/run/docker.sock \
    --network futurekawa-jenkins \
    jenkins-futurekawa:local

echo ""
echo -e "${GREEN}✅ Jenkins démarré${NC}"
echo ""

# ── Attente que Jenkins soit prêt ─────────────────────────────
echo -e "${YELLOW}[5] Attente du démarrage de Jenkins (120s max)...${NC}"
MAX=24; COUNT=0
until curl -sf http://localhost:8081/login > /dev/null 2>&1 || [ $COUNT -eq $MAX ]; do
    echo "  Démarrage en cours... ($((COUNT*5))s)"
    sleep 5
    COUNT=$((COUNT+1))
done

if ! curl -sf http://localhost:8081/login > /dev/null 2>&1; then
    echo -e "${RED}❌ Jenkins ne démarre pas — vérifie : docker logs jenkins-futurekawa${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Jenkins est en ligne sur http://localhost:8081${NC}"
echo ""

# ── Vérification docker-cli dans le conteneur ─────────────────
echo -e "${YELLOW}[6] Vérification docker-cli dans Jenkins...${NC}"
if docker exec jenkins-futurekawa docker version > /dev/null 2>&1; then
    echo -e "${GREEN}✅ docker-cli accessible depuis Jenkins${NC}"
else
    echo -e "${RED}⚠️  docker-cli non accessible — le socket est peut-être mal monté${NC}"
    echo "    Vérifie que Docker Desktop > Settings > General > 'Expose daemon on tcp...' est OFF"
    echo "    et que WSL integration est activée pour ta distro"
fi
echo ""

# ── Récupération du mot de passe initial ─────────────────────
echo -e "${YELLOW}[7] Récupération du mot de passe administrateur initial...${NC}"
sleep 5
INITIAL_PWD=$(docker exec jenkins-futurekawa \
    cat /var/jenkins_home/secrets/initialAdminPassword 2>/dev/null || echo "Pas encore disponible")

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Jenkins est installé et prêt !                  ║${NC}"
echo -e "${BLUE}║                                                   ║${NC}"
echo -e "${BLUE}║  URL     : http://localhost:8081                  ║${NC}"
echo -e "${BLUE}║  Password: ${INITIAL_PWD}  ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}→ Ouvre http://localhost:8081 dans ton navigateur${NC}"
echo -e "${YELLOW}→ Entre le mot de passe ci-dessus${NC}"
echo -e "${YELLOW}→ Clique sur 'Install suggested plugins'${NC}"
echo -e "${YELLOW}→ Crée un compte admin${NC}"
echo ""
echo "Pour relancer Jenkins :"
echo "  docker start jenkins-futurekawa"
echo ""
echo "Pour voir les logs :"
echo "  docker logs -f jenkins-futurekawa"