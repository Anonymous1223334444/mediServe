echo "🛑 Arrêt des services MediRecord..."

# Fonction pour arrêter un service
stop_service() {
    if [ -f pids/$1.pid ]; then
        PID=$(cat pids/$1.pid)
        if ps -p $PID > /dev/null; then
            echo "⏹️ Arrêt de $1 (PID: $PID)..."
            kill $PID
        fi
        rm pids/$1.pid
    fi
}

# Arrêter tous les services
stop_service "celery-worker"
stop_service "celery-beat"
stop_service "django"
stop_service "ngrok-django"
stop_service "ngrok-n8n"

# Arrêter le container N8N
echo "🤖 Arrêt du container N8N..."
sudo docker stop n8n-medirecord
sudo docker rm n8n-medirecord

# Nettoyer
rmdir pids 2>/dev/null

echo "✅ Tous les services sont arrêtés!"

# install_frontend.sh - Installation du frontend Next.js
#!/bin/bash

echo "🎨 Installation du frontend Next.js..."

# Vérifier si Node.js est installé
if ! command -v node &> /dev/null; then
    echo "❌ Node.js n'est pas installé. Installation..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# Installer les dépendances
echo "📦 Installation des dépendances npm..."
npm install

# Créer le fichier .env.local pour Next.js
if [ ! -f .env.local ]; then
    echo "⚙️ Configuration de .env.local..."
    cat > .env.local << EOL
NEXT_PUBLIC_DJANGO_API_BASE_URL=https://inspired-shrew-usually.ngrok-free.app
EOL
fi

echo "✅ Frontend configuré!"
echo "🚀 Pour démarrer: npm run dev"
