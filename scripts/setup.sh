#!/bin/bash

echo "🚀 Configuration de MediRecord SIS..."

# 1. Créer et activer l'environnement virtuel
echo "📦 Création de l'environnement virtuel..."
python3 -m venv venv
source venv/bin/activate

# 2. Installer les dépendances Python
echo "📥 Installation des dépendances Python..."
pip install --upgrade pip
pip install -r requirements.txt

# 3. Installer Redis (sur Ubuntu/Debian)
echo "📡 Installation de Redis..."
sudo apt update
sudo apt install -y redis-server
sudo systemctl start redis
sudo systemctl enable redis

# 4. Installer PostgreSQL (optionnel, SQLite par défaut)
read -p "Voulez-vous installer PostgreSQL? (y/n): " install_postgres
if [ "$install_postgres" = "y" ]; then
    echo "🐘 Installation de PostgreSQL..."
    sudo apt install -y postgresql postgresql-contrib
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    
    # Créer la base de données
    sudo -u postgres createdb medirecord
    sudo -u postgres createuser medirecord_user
    sudo -u postgres psql -c "ALTER USER medirecord_user WITH PASSWORD 'your_password';"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE medirecord TO medirecord_user;"
fi

# 5. Installer Tesseract pour OCR
echo "👁️ Installation de Tesseract OCR..."
sudo apt install -y tesseract-ocr tesseract-ocr-fra

# 6. Copier et configurer .env
if [ ! -f .env ]; then
    echo "⚙️ Configuration du fichier .env..."
    cp .env.example .env
    echo "✅ Fichier .env créé. Veuillez le modifier avec vos clés API."
fi

# 7. Créer les apps Django manquantes
echo "🏗️ Création des applications Django..."
python manage.py startapp documents
python manage.py startapp rag
python manage.py startapp messaging

# 8. Migrations Django
echo "🗄️ Migrations de la base de données..."
python manage.py makemigrations
python manage.py makemigrations patients
python manage.py makemigrations documents
python manage.py makemigrations rag  
python manage.py makemigrations messaging
python manage.py migrate

# 9. Créer un superutilisateur
echo "👤 Création du superutilisateur..."
python manage.py createsuperuser

echo "✅ Configuration terminée!"
echo ""
echo "📋 Étapes suivantes:"
echo "1. Modifiez le fichier .env avec vos vraies clés API"
echo "2. Configurez Pinecone et créez votre index"
echo "3. Configurez votre compte Twilio WhatsApp"
echo "4. Lancez les services avec: ./start_services.sh"
