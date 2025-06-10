#!/bin/bash

echo "🚀 Démarrage des services MediRecord..."

# Activer l'environnement virtuel
source venv/bin/activate

# Fonction pour lancer un service en arrière-plan
start_service() {
    echo "🔄 Démarrage de $1..."
    $2 &
    echo $! > pids/$1.pid
}

# Créer le dossier pour les PIDs
mkdir -p pids

# 1. Démarrer Redis (si pas déjà actif)
if ! pgrep redis-server > /dev/null; then
    echo "📡 Démarrage de Redis..."
    redis-server &
fi

# 2. Démarrer Celery Worker
start_service "celery-worker" "celery -A mediServe worker --loglevel=info"

# 3. Démarrer Celery Beat (pour les tâches programmées)
start_service "celery-beat" "celery -A mediServe beat --loglevel=info"

# 4. Démarrer N8N (Docker)
echo "🤖 Démarrage de N8N..."
sudo docker run -d --name n8n-medirecord \
  -p 5678:5678 \
  -e WEBHOOK_URL=https://orca-eternal-specially.ngrok-free.app \
  -e N8N_HOST=orca-eternal-specially.ngrok-free.app \
  -e N8N_LOG_LEVEL=debug \
  -v n8n_data:/home/node/.n8n \
  docker.n8n.io/n8nio/n8n

# 5. Démarrer Django
echo "🐍 Démarrage de Django..."
python manage.py runserver 8000 &
echo $! > pids/django.pid

# 6. Démarrer ngrok pour Django
echo "🌐 Démarrage de ngrok pour Django..."
ngrok http --url=https://inspired-shrew-usually.ngrok-free.app 8000 &
echo $! > pids/ngrok-django.pid

# 7. Démarrer ngrok pour N8N
echo "🌐 Démarrage de ngrok pour N8N..."
ngrok http --url=orca-eternal-specially.ngrok-free.app 5678 &
echo $! > pids/ngrok-n8n.pid

echo "✅ Tous les services sont démarrés!"
echo ""
echo "📡 URLs d'accès:"
echo "  Django API: https://inspired-shrew-usually.ngrok-free.app"
echo "  N8N Interface: https://orca-eternal-specially.ngrok-free.app"
echo "  Django Admin: https://inspired-shrew-usually.ngrok-free.app/admin"
echo "  API Docs: https://inspired-shrew-usually.ngrok-free.app/swagger"
echo ""
echo "🛑 Pour arrêter tous les services: ./stop_services.sh"
