#!/bin/bash
# Script pour exécuter les tests depuis n'importe quel répertoire

# Déterminer le répertoire du script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Si on est dans le dossier scripts, remonter d'un niveau
if [[ "$(basename "$SCRIPT_DIR")" == "scripts" ]]; then
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
else
    PROJECT_ROOT="$SCRIPT_DIR"
fi

echo "📁 Répertoire du projet: $PROJECT_ROOT"

# Aller dans le répertoire du projet
cd "$PROJECT_ROOT" || exit 1

# Activer l'environnement virtuel si disponible
if [ -f "venv/bin/activate" ]; then
    echo "🔧 Activation de l'environnement virtuel..."
    source venv/bin/activate
fi

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "manage.py" ]; then
    echo "❌ Erreur: manage.py non trouvé!"
    echo "   Répertoire actuel: $(pwd)"
    exit 1
fi

# Définir les variables d'environnement
export DJANGO_SETTINGS_MODULE=mediServe.settings
export PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH

# Exécuter la commande demandée
if [ $# -eq 0 ]; then
    echo "Usage: $0 <commande>"
    echo ""
    echo "Commandes disponibles:"
    echo "  verify     - Vérifier la configuration"
    echo "  redis      - Tester Redis/Celery"
    echo "  celery     - Tester la connexion Celery"
    echo "  direct ID  - Tester la vectorisation directe"
    echo "  task ID    - Tester la tâche Celery"
    echo "  all ID     - Tout tester"
    exit 1
fi

COMMAND=$1

case $COMMAND in
    verify)
        echo "🔍 Vérification de la configuration..."
        python scripts/verify_setup.py
        ;;
    redis)
        echo "🔴 Test Redis/Celery..."
        python scripts/check_redis.py
        ;;
    celery)
        echo "🌿 Test connexion Celery..."
        python scripts/test_celery_vectorization.py celery
        ;;
    direct)
        if [ -z "$2" ]; then
            echo "❌ ID du document requis!"
            exit 1
        fi
        echo "🔄 Test vectorisation directe (ID: $2)..."
        python scripts/test_celery_vectorization.py direct "$2"
        ;;
    task)
        if [ -z "$2" ]; then
            echo "❌ ID du document requis!"
            exit 1
        fi
        echo "📋 Test tâche Celery (ID: $2)..."
        python scripts/test_celery_vectorization.py task "$2"
        ;;
    all)
        if [ -z "$2" ]; then
            echo "❌ ID du document requis!"
            exit 1
        fi
        echo "🧪 Tests complets (ID: $2)..."
        python scripts/test_celery_vectorization.py all "$2"
        ;;
    *)
        echo "❌ Commande inconnue: $COMMAND"
        exit 1
        ;;
esac