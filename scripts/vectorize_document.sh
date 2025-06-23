#!/bin/bash
# Script de vectorisation pour un document
# Usage: ./vectorize_document.sh <document_upload_id>

# Configuration avec logs détaillés
set -e  # Arrêter en cas d'erreur
set -x  # Afficher toutes les commandes exécutées

echo "🚀 === DÉBUT SCRIPT VECTORIZE_DOCUMENT.SH ==="
echo "📅 Date: $(date)"
echo "👤 Utilisateur: $(whoami)"
echo "📁 Répertoire actuel: $(pwd)"

# Configuration des chemins
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"


echo "📁 SCRIPT_DIR: $SCRIPT_DIR"
echo "📁 PROJECT_ROOT: $PROJECT_ROOT"

# Vérifier les arguments
if [ $# -eq 0 ]; then
    echo "❌ Usage: $0 <document_upload_id>"
    exit 1
fi

DOCUMENT_ID=$1
echo "📄 Document ID: $DOCUMENT_ID"

# Déterminer le chemin Python
if [ -f "$PROJECT_ROOT/venv/bin/python" ]; then
    PYTHON_PATH="$PROJECT_ROOT/venv/bin/python"
    echo "🐍 Utilisation du venv Python: $PYTHON_PATH"
elif command -v python3.12 &> /dev/null; then
    PYTHON_PATH="python3.12"
    echo "🐍 Utilisation de python3.12 système"
elif command -v python3 &> /dev/null; then
    PYTHON_PATH="python3"
    echo "🐍 Utilisation de python3 système"
else
    echo "❌ Python non trouvé!"
    exit 1
fi

# Vérifier la version Python
echo "🐍 Version Python:"
$PYTHON_PATH --version

# Activer l'environnement virtuel si disponible
if [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    echo "🔧 Activation du venv..."
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Définir les variables d'environnement
export DJANGO_SETTINGS_MODULE=mediServe.settings
export PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH

echo "🔧 Variables d'environnement:"
echo "   DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"
echo "   PYTHONPATH=$PYTHONPATH"

# Vérifier que le script Python existe
VECTORIZE_SCRIPT="$SCRIPT_DIR/vectorize_single_document.py"
if [ ! -f "$VECTORIZE_SCRIPT" ]; then
    echo "❌ Script Python non trouvé: $VECTORIZE_SCRIPT"
    echo "📁 Contenu du dossier scripts:"
    ls -la "$SCRIPT_DIR"
    exit 1
fi

echo "✅ Script Python trouvé: $VECTORIZE_SCRIPT"

# Aller dans le répertoire du projet
cd "$PROJECT_ROOT"
echo "📁 Changement vers: $(pwd)"

# Exécuter le script Python de vectorisation
echo "🚀 Exécution du script Python..."
echo "🔧 Commande: $PYTHON_PATH $VECTORIZE_SCRIPT $DOCUMENT_ID"

$PYTHON_PATH "$VECTORIZE_SCRIPT" $DOCUMENT_ID

# Capturer le code de retour
EXIT_CODE=$?
echo "🏁 Code de retour: $EXIT_CODE"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Vectorisation réussie pour le document $DOCUMENT_ID"
else
    echo "❌ Échec de la vectorisation (code: $EXIT_CODE)"
fi

echo "🏁 === FIN SCRIPT VECTORIZE_DOCUMENT.SH ==="
exit $EXIT_CODE