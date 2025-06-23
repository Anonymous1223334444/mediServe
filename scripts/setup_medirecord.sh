#!/bin/bash

# Script de configuration pour MediRecord
# Crée tous les dossiers nécessaires et configure les permissions

echo "🚀 Configuration de MediRecord..."

# Déterminer le répertoire du projet
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📁 Répertoire du projet: $PROJECT_ROOT"

# Créer les dossiers nécessaires
echo "📂 Création des dossiers..."

# Dossiers media
mkdir -p "$PROJECT_ROOT/media/patient_documents"
mkdir -p "$PROJECT_ROOT/media/vectors"
mkdir -p "$PROJECT_ROOT/media/indexes"

# Dossiers logs
mkdir -p "$PROJECT_ROOT/logs"

# Dossiers scripts
mkdir -p "$PROJECT_ROOT/scripts"

# Donner les permissions d'exécution aux scripts
echo "🔧 Configuration des permissions..."
chmod +x "$PROJECT_ROOT/scripts/"*.sh 2>/dev/null
chmod +x "$PROJECT_ROOT/scripts/"*.py 2>/dev/null

# Installer les dépendances Python si nécessaire
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo "📦 Installation des dépendances Python..."
    pip install -r "$PROJECT_ROOT/requirements.txt"
fi

# Télécharger les modèles NLTK
echo "📚 Téléchargement des modèles NLTK..."
python3 -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')" 2>/dev/null

# Installer Tesseract si nécessaire (pour OCR)
if ! command -v tesseract &> /dev/null; then
    echo "⚠️  Tesseract n'est pas installé. Installation recommandée:"
    echo "    Ubuntu/Debian: sudo apt-get install tesseract-ocr tesseract-ocr-fra"
    echo "    MacOS: brew install tesseract tesseract-lang"
fi

# Créer le fichier .env si nécessaire
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "📝 Création du fichier .env..."
    cat > "$PROJECT_ROOT/.env" << EOF
# Django
DJANGO_SECRET_KEY=your-secret-key-here

# Database
POSTGRES_DB=mediserve
POSTGRES_USER=mediserve
POSTGRES_PASSWORD=your-password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Twilio
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_VERIFY_SID=your-verify-sid
TWILIO_WHATSAPP_NUMBER=+14155238886

# Google Gemini
GEMINI_API_KEY=your-gemini-api-key

# Pinecone
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX_NAME=medirecord-rag

# N8N
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your-n8n-api-key

# Site
SITE_PUBLIC_URL=http://localhost:8000
EOF
    echo "⚠️  N'oubliez pas de configurer les clés API dans .env"
fi

# Appliquer les migrations
echo "🗄️  Application des migrations Django..."
cd "$PROJECT_ROOT"
python manage.py migrate

# Collecter les fichiers statiques
echo "📦 Collecte des fichiers statiques..."
python manage.py collectstatic --noinput 2>/dev/null || true

echo "✅ Configuration terminée!"
echo ""
echo "📋 Prochaines étapes:"
echo "1. Configurez les clés API dans .env"
echo "2. Lancez Redis: redis-server"
echo "3. Lancez Celery: celery -A mediServe worker -l info"
echo "4. Lancez Celery Beat: celery -A mediServe beat -l info"
echo "5. Lancez Django: python manage.py runserver"
echo "6. Lancez le frontend: npm run dev"