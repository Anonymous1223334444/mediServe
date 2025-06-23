#!/bin/bash
# Script d'installation et de configuration du projet MediServe

echo "🚀 === INSTALLATION MEDISERVE ==="
echo "📅 Date: $(date)"

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction pour afficher les messages
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_info() { echo -e "ℹ️  $1"; }

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "manage.py" ]; then
    log_error "Ce script doit être exécuté depuis la racine du projet Django!"
    exit 1
fi

PROJECT_ROOT=$(pwd)
log_info "Répertoire du projet: $PROJECT_ROOT"

# 1. Installer les dépendances système
log_info "Installation des dépendances système..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    postgresql \
    postgresql-contrib \
    redis-server \
    tesseract-ocr \
    tesseract-ocr-fra \
    poppler-utils \
    libpoppler-cpp-dev \
    build-essential \
    libssl-dev \
    libffi-dev

# 2. Créer l'environnement virtuel Python
log_info "Création de l'environnement virtuel..."
if [ ! -d "venv" ]; then
    python3.12 -m venv venv
    log_success "Environnement virtuel créé"
else
    log_warning "Environnement virtuel déjà existant"
fi

# Activer l'environnement virtuel
source venv/bin/activate
log_success "Environnement virtuel activé"

# 3. Mettre à jour pip
log_info "Mise à jour de pip..."
pip install --upgrade pip setuptools wheel

# 4. Installer les dépendances Python
log_info "Installation des dépendances Python..."
pip install -r requirements.txt

# 5. Télécharger les modèles NLTK
log_info "Téléchargement des modèles NLTK..."
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"

# 6. Créer les répertoires nécessaires
log_info "Création des répertoires..."
mkdir -p logs
mkdir -p media/patient_documents
mkdir -p media/vectors
mkdir -p media/indexes
mkdir -p scripts

# 7. Définir les permissions
chmod -R 755 scripts/
chmod +x scripts/*.sh
chmod +x scripts/*.py

# 8. Vérifier Redis
log_info "Vérification de Redis..."
sudo systemctl start redis
if redis-cli ping > /dev/null 2>&1; then
    log_success "Redis fonctionne correctement"
else
    log_error "Redis ne répond pas!"
fi

# 9. Créer le fichier .env s'il n'existe pas
if [ ! -f ".env" ]; then
    log_info "Création du fichier .env..."
    cat > .env << EOF
# Django
DJANGO_SECRET_KEY='your-secret-key-here'
DEBUG=True

# Database
POSTGRES_DB=mediserve
POSTGRES_USER=mediserve
POSTGRES_PASSWORD=mediserve123
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis/Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Twilio
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_VERIFY_SID=your-verify-sid
TWILIO_WHATSAPP_NUMBER=+1234567890

# Google Gemini
GEMINI_API_KEY=your-gemini-key

# Pinecone (optionnel)
PINECONE_API_KEY=your-pinecone-key
PINECONE_INDEX_NAME=medirecord-rag

# N8N
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your-n8n-key

# Site
SITE_PUBLIC_URL=http://127.0.0.1:8000
EOF
    log_warning "Fichier .env créé - PENSEZ À LE CONFIGURER!"
else
    log_info "Fichier .env déjà existant"
fi

# 10. Configurer la base de données
log_info "Configuration de PostgreSQL..."
sudo -u postgres psql << EOF
CREATE DATABASE mediserve;
CREATE USER mediserve WITH PASSWORD 'mediserve123';
GRANT ALL PRIVILEGES ON DATABASE mediserve TO mediserve;
\q
EOF

# 11. Appliquer les migrations
log_info "Application des migrations Django..."
python manage.py makemigrations
python manage.py migrate

# 12. Créer le superutilisateur
log_info "Création du superutilisateur (optionnel)..."
echo "Voulez-vous créer un superutilisateur maintenant? (y/n)"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    python manage.py createsuperuser
fi

# 13. Collecter les fichiers statiques
log_info "Collection des fichiers statiques..."
python manage.py collectstatic --noinput

# 14. Créer les scripts de démarrage
log_info "Création des scripts de démarrage..."

# Script pour démarrer tous les services
cat > start_services.sh << 'EOF'
#!/bin/bash
echo "🚀 Démarrage des services MediServe..."

# Démarrer Redis
sudo systemctl start redis
echo "✅ Redis démarré"

# Activer l'environnement virtuel
source venv/bin/activate

# Démarrer Celery Worker dans un nouveau terminal
gnome-terminal --tab --title="Celery Worker" -- bash -c "source venv/bin/activate && celery -A mediServe worker -l info; exec bash"

# Démarrer Celery Beat dans un nouveau terminal
gnome-terminal --tab --title="Celery Beat" -- bash -c "source venv/bin/activate && celery -A mediServe beat -l info; exec bash"

# Démarrer Django dans un nouveau terminal
gnome-terminal --tab --title="Django Server" -- bash -c "source venv/bin/activate && python manage.py runserver; exec bash"

echo "✅ Tous les services démarrés!"
echo "📋 Services en cours:"
echo "   - Redis: port 6379"
echo "   - Django: http://localhost:8000"
echo "   - Celery Worker: voir terminal"
echo "   - Celery Beat: voir terminal"
EOF

chmod +x start_services.sh

# 15. Test final
log_info "Tests finaux..."

# Test Python et Django
python -c "import django; print(f'Django {django.__version__} OK')"

# Test des imports critiques
python << EOF
try:
    import sentence_transformers
    print("✅ sentence_transformers OK")
except:
    print("❌ sentence_transformers ERREUR")

try:
    import whoosh
    print("✅ whoosh OK")
except:
    print("❌ whoosh ERREUR")

try:
    import faiss
    print("✅ faiss OK")
except:
    print("❌ faiss ERREUR")
EOF

log_success "Installation terminée!"
echo ""
echo "📋 Prochaines étapes:"
echo "1. Configurer le fichier .env avec vos clés API"
echo "2. Lancer les services avec: ./start_services.sh"
echo "3. Créer un patient de test"
echo "4. Vérifier les logs dans le dossier logs/"
echo ""
echo "🧪 Pour tester le système:"
echo "   python scripts/check_redis.py"
echo "   python scripts/test_celery_vectorization.py celery"