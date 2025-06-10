#!/bin/bash

set -e

PROJECT_NAME="medirecord-sis"
DEPLOY_USER="medirecord"
DEPLOY_PATH="/home/$DEPLOY_USER/$PROJECT_NAME"
BACKUP_PATH="/backup/medirecord"
SERVICE_NAME="medirecord"

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[DEPLOY]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Vérifier les prérequis
check_prerequisites() {
    log "Vérification des prérequis..."
    
    # Vérifier que nous sommes sur le serveur de production
    if [[ ! -f "/home/$DEPLOY_USER/.deploy_target" ]]; then
        error "Ce script doit être exécuté sur le serveur de production"
    fi
    
    # Vérifier que Git est configuré
    if ! command -v git &> /dev/null; then
        error "Git n'est pas installé"
    fi
    
    # Vérifier les services
    for service in postgresql redis nginx; do
        if ! systemctl is-active --quiet $service; then
            error "Service $service n'est pas actif"
        fi
    done
}

# Sauvegarde de sécurité
backup_current() {
    log "Création d'une sauvegarde de sécurité..."
    
    DATE=$(date +%Y%m%d_%H%M%S)
    mkdir -p "$BACKUP_PATH"
    
    # Backup base de données
    sudo -u postgres pg_dump medirecord_prod > "$BACKUP_PATH/pre_deploy_db_$DATE.sql"
    
    # Backup fichiers
    tar -czf "$BACKUP_PATH/pre_deploy_files_$DATE.tar.gz" -C "$DEPLOY_PATH" . --exclude=venv --exclude=.git
    
    echo "$DATE" > "$BACKUP_PATH/last_deploy_backup.txt"
    log "Sauvegarde créée: pre_deploy_$DATE"
}

# Déploiement du code
deploy_code() {
    log "Déploiement du code..."
    
    cd "$DEPLOY_PATH"
    
    # Récupérer les dernières modifications
    sudo -u $DEPLOY_USER git fetch origin
    
    # Vérifier qu'il y a des changements
    if git diff HEAD origin/main --quiet; then
        log "Aucun changement détecté, déploiement annulé"
        exit 0
    fi
    
    # Arrêter les services
    systemctl stop $SERVICE_NAME ${SERVICE_NAME}-celery
    
    # Mettre à jour le code
    sudo -u $DEPLOY_USER git pull origin main
    
    # Activer l'environnement virtuel et installer les dépendances
    sudo -u $DEPLOY_USER bash -c "
        source venv/bin/activate
        pip install -r requirements.txt
        python manage.py migrate
        python manage.py collectstatic --noinput
    "
}

# Tests de déploiement
run_tests() {
    log "Exécution des tests..."
    
    cd "$DEPLOY_PATH"
    sudo -u $DEPLOY_USER bash -c "
        source venv/bin/activate
        python manage.py test --keepdb --parallel 4
    " || {
        error "Les tests ont échoué, déploiement interrompu"
    }
}

# Redémarrer les services
restart_services() {
    log "Redémarrage des services..."
    
    systemctl start $SERVICE_NAME ${SERVICE_NAME}-celery
    systemctl reload nginx
    
    # Attendre que les services soient prêts
    sleep 10
    
    # Vérifier que l'API répond
    for i in {1..30}; do
        if curl -f -s http://localhost:8000/api/health/ > /dev/null; then
            log "API opérationnelle"
            break
        fi
        
        if [[ $i -eq 30 ]]; then
            error "L'API ne répond pas après le déploiement"
        fi
        
        sleep 2
    done
}

# Tests post-déploiement
post_deploy_tests() {
    log "Tests post-déploiement..."
    
    # Test API
    if ! curl -f -s http://localhost:8000/api/health/ | grep -q "healthy"; then
        error "Health check API échoué"
    fi
    
    # Test création patient (mock)
    cd "$DEPLOY_PATH"
    sudo -u $DEPLOY_USER bash -c "
        source venv/bin/activate
        python manage.py shell -c \"
from patients.models import Patient
from django.db import transaction
with transaction.atomic():
    p = Patient.objects.create(
        first_name='Test',
        last_name='Deploy',
        phone='+221700000000',
        email='test@deploy.com',
        date_of_birth='1990-01-01',
        gender='M'
    )
    print(f'Test patient créé: {p.id}')
    p.delete()
    print('Test patient supprimé')
\"
    " || {
        error "Test de création patient échoué"
    }
}

# Nettoyage post-déploiement
cleanup() {
    log "Nettoyage post-déploiement..."
    
    # Nettoyer les anciens logs
    find /var/log/medirecord -name "*.log.*" -mtime +7 -delete
    
    # Nettoyer les anciennes sauvegardes
    find "$BACKUP_PATH" -name "pre_deploy_*" -mtime +7 -delete
    
    # Redémarrer les tâches Celery pour prendre en compte les nouveaux codes
    systemctl restart ${SERVICE_NAME}-celery
}

# Rollback en cas d'erreur
rollback() {
    error "Erreur détectée, rollback en cours..."
    
    if [[ -f "$BACKUP_PATH/last_deploy_backup.txt" ]]; then
        BACKUP_DATE=$(cat "$BACKUP_PATH/last_deploy_backup.txt")
        
        # Arrêter les services
        systemctl stop $SERVICE_NAME ${SERVICE_NAME}-celery
        
        # Restaurer la base de données
        sudo -u postgres dropdb medirecord_prod
        sudo -u postgres createdb medirecord_prod
        sudo -u postgres psql medirecord_prod < "$BACKUP_PATH/pre_deploy_db_$BACKUP_DATE.sql"
        
        # Restaurer les fichiers
        cd "$DEPLOY_PATH"
        sudo -u $DEPLOY_USER tar -xzf "$BACKUP_PATH/pre_deploy_files_$BACKUP_DATE.tar.gz"
        
        # Redémarrer les services
        systemctl start $SERVICE_NAME ${SERVICE_NAME}-celery
        
        log "Rollback terminé"
    else
        error "Impossible de faire un rollback, aucune sauvegarde trouvée"
    fi
}

# Trap pour gérer les erreurs
trap rollback ERR

# Déploiement principal
main() {
    log "Début du déploiement MediRecord"
    
    check_prerequisites
    backup_current
    deploy_code
    run_tests
    restart_services
    post_deploy_tests
    cleanup
    
    log "Déploiement terminé avec succès!"
    
    # Afficher le statut final
    "$DEPLOY_PATH/scripts/admin.sh" status
}

# Exécution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
