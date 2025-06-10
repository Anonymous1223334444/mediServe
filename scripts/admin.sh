#!/bin/bash
# scripts/admin.sh - Script d'administration principal

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/medirecord/medirecord-sis"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="/var/log/medirecord"
BACKUP_DIR="/backup/medirecord"
SERVICE_NAME="medirecord"

# Fonctions utilitaires
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Vérifier les permissions
check_permissions() {
    if [[ $EUID -ne 0 ]] && [[ "$1" != "status" ]] && [[ "$1" != "logs" ]]; then
        log_error "Ce script doit être exécuté en tant que root pour la plupart des opérations."
        log_info "Utilisez: sudo $0 $1"
        exit 1
    fi
}

# Fonction pour activer l'environnement virtuel
activate_venv() {
    if [[ -f "$VENV_DIR/bin/activate" ]]; then
        source "$VENV_DIR/bin/activate"
        log_info "Environnement virtuel activé"
    else
        log_error "Environnement virtuel non trouvé: $VENV_DIR"
        exit 1
    fi
}

# 1. STATUS - Vérifier l'état des services
cmd_status() {
    log_step "Vérification de l'état des services MediRecord"
    
    services=("medirecord" "medirecord-celery" "nginx" "postgresql" "redis")
    
    for service in "${services[@]}"; do
        if systemctl is-active --quiet "$service"; then
            echo -e "$service: ${GREEN}✓ ACTIF${NC}"
        else
            echo -e "$service: ${RED}✗ INACTIF${NC}"
        fi
    done
    
    echo ""
    log_step "Vérification de l'API Health Check"
    
    if curl -f -s http://localhost:8000/api/health/ > /dev/null; then
        echo -e "API Health: ${GREEN}✓ OK${NC}"
    else
        echo -e "API Health: ${RED}✗ ERREUR${NC}"
    fi
    
    echo ""
    log_step "Utilisation des ressources"
    
    # CPU et mémoire
    echo "CPU: $(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1"%"}')"
    echo "RAM: $(free | grep Mem | awk '{printf "%.1f%%", $3/$2 * 100.0}')"
    echo "Disk: $(df -h / | awk 'NR==2{print $5}')"
    
    # Connexions base de données
    db_connections=$(sudo -u postgres psql medirecord_prod -t -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null || echo "N/A")
    echo "DB Connections: $db_connections"
    
    # Redis
    redis_memory=$(redis-cli info memory | grep used_memory_human | cut -d: -f2 | tr -d '\r' 2>/dev/null || echo "N/A")
    echo "Redis Memory: $redis_memory"
}

# 2. LOGS - Afficher les logs
cmd_logs() {
    log_step "Affichage des logs MediRecord"
    
    case "$2" in
        "django"|"")
            log_info "Logs Django (dernières 50 lignes):"
            tail -n 50 "$LOG_DIR/django.log" 2>/dev/null || log_warning "Fichier de log Django non trouvé"
            ;;
        "celery")
            log_info "Logs Celery (dernières 50 lignes):"
            tail -n 50 "$LOG_DIR/celery.log" 2>/dev/null || log_warning "Fichier de log Celery non trouvé"
            ;;
        "nginx")
            log_info "Logs Nginx (dernières 20 lignes):"
            tail -n 20 /var/log/nginx/error.log 2>/dev/null || log_warning "Fichier de log Nginx non trouvé"
            ;;
        "all")
            echo "=== DJANGO ==="
            tail -n 20 "$LOG_DIR/django.log" 2>/dev/null || echo "Pas de logs Django"
            echo -e "\n=== CELERY ==="
            tail -n 20 "$LOG_DIR/celery.log" 2>/dev/null || echo "Pas de logs Celery"
            echo -e "\n=== NGINX ==="
            tail -n 20 /var/log/nginx/error.log 2>/dev/null || echo "Pas de logs Nginx"
            ;;
        *)
            log_error "Type de log invalide. Utilisez: django, celery, nginx, all"
            ;;
    esac
}

# 3. RESTART - Redémarrer les services
cmd_restart() {
    log_step "Redémarrage des services MediRecord"
    
    case "$2" in
        "django"|"")
            log_info "Redémarrage Django..."
            systemctl restart medirecord
            systemctl restart medirecord-celery
            ;;
        "nginx")
            log_info "Redémarrage Nginx..."
            systemctl restart nginx
            ;;
        "all")
            log_info "Redémarrage de tous les services..."
            systemctl restart medirecord
            systemctl restart medirecord-celery
            systemctl restart nginx
            systemctl restart redis
            ;;
        *)
            log_error "Service invalide. Utilisez: django, nginx, all"
            exit 1
            ;;
    esac
    
    sleep 3
    cmd_status
}

# 4. BACKUP - Sauvegarder le système
cmd_backup() {
    log_step "Sauvegarde du système MediRecord"
    
    DATE=$(date +%Y%m%d_%H%M%S)
    mkdir -p "$BACKUP_DIR"
    
    # Backup base de données
    log_info "Sauvegarde de la base de données..."
    sudo -u postgres pg_dump medirecord_prod > "$BACKUP_DIR/db_$DATE.sql"
    
    # Backup fichiers media
    log_info "Sauvegarde des fichiers media..."
    tar -czf "$BACKUP_DIR/media_$DATE.tar.gz" -C "$PROJECT_DIR" media/
    
    # Backup configuration
    log_info "Sauvegarde de la configuration..."
    cp "$PROJECT_DIR/.env" "$BACKUP_DIR/env_$DATE.backup"
    
    # Backup N8N workflows
    log_info "Sauvegarde des workflows N8N..."
    docker exec medirecord_n8n n8n export:workflow --backup --output="/home/node/.n8n/backups/workflows_$DATE.json" 2>/dev/null || log_warning "Backup N8N échoué"
    
    # Compression finale
    log_info "Compression de la sauvegarde..."
    tar -czf "$BACKUP_DIR/full_backup_$DATE.tar.gz" -C "$BACKUP_DIR" \
        "db_$DATE.sql" "media_$DATE.tar.gz" "env_$DATE.backup"
    
    # Nettoyage des fichiers temporaires
    rm -f "$BACKUP_DIR/db_$DATE.sql" "$BACKUP_DIR/media_$DATE.tar.gz" "$BACKUP_DIR/env_$DATE.backup"
    
    log_info "Sauvegarde terminée: $BACKUP_DIR/full_backup_$DATE.tar.gz"
    
    # Nettoyage automatique (garder 30 jours)
    find "$BACKUP_DIR" -name "full_backup_*.tar.gz" -mtime +30 -delete
    
    log_info "Anciennes sauvegardes supprimées (>30 jours)"
}

# 5. RESTORE - Restaurer depuis une sauvegarde
cmd_restore() {
    if [[ -z "$2" ]]; then
        log_error "Usage: $0 restore <fichier_backup.tar.gz>"
        exit 1
    fi
    
    BACKUP_FILE="$2"
    
    if [[ ! -f "$BACKUP_FILE" ]]; then
        log_error "Fichier de sauvegarde non trouvé: $BACKUP_FILE"
        exit 1
    fi
    
    log_warning "ATTENTION: Cette opération va écraser les données actuelles!"
    read -p "Êtes-vous sûr de vouloir continuer? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Restauration annulée"
        exit 0
    fi
    
    log_step "Restauration depuis $BACKUP_FILE"
    
    # Arrêter les services
    log_info "Arrêt des services..."
    systemctl stop medirecord medirecord-celery
    
    # Extraire la sauvegarde
    TEMP_DIR=$(mktemp -d)
    tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"
    
    # Restaurer la base de données
    log_info "Restauration de la base de données..."
    sudo -u postgres dropdb medirecord_prod
    sudo -u postgres createdb medirecord_prod
    sudo -u postgres psql medirecord_prod < "$TEMP_DIR"/*.sql
    
    # Restaurer les fichiers media
    log_info "Restauration des fichiers media..."
    rm -rf "$PROJECT_DIR/media"
    tar -xzf "$TEMP_DIR"/media_*.tar.gz -C "$PROJECT_DIR"
    
    # Redémarrer les services
    log_info "Redémarrage des services..."
    systemctl start medirecord medirecord-celery
    
    # Nettoyage
    rm -rf "$TEMP_DIR"
    
    log_info "Restauration terminée avec succès"
}

# 6. UPDATE - Mettre à jour le système
cmd_update() {
    log_step "Mise à jour du système MediRecord"
    
    cd "$PROJECT_DIR"
    
    # Backup automatique avant mise à jour
    log_info "Création d'une sauvegarde de sécurité..."
    cmd_backup
    
    # Arrêter les services
    log_info "Arrêt des services..."
    systemctl stop medirecord medirecord-celery
    
    # Activer l'environnement virtuel
    activate_venv
    
    # Mise à jour du code
    log_info "Mise à jour du code depuis Git..."
    git pull origin main
    
    # Mise à jour des dépendances
    log_info "Mise à jour des dépendances Python..."
    pip install -r requirements.txt
    
    # Migrations de base de données
    log_info "Application des migrations..."
    python manage.py migrate
    
    # Collecte des fichiers statiques
    log_info "Collecte des fichiers statiques..."
    python manage.py collectstatic --noinput
    
    # Redémarrage des services
    log_info "Redémarrage des services..."
    systemctl start medirecord medirecord-celery
    systemctl reload nginx
    
    log_info "Mise à jour terminée avec succès"
}

# 7. MAINTENANCE - Opérations de maintenance
cmd_maintenance() {
    log_step "Opérations de maintenance MediRecord"
    
    activate_venv
    cd "$PROJECT_DIR"
    
    # Nettoyage des logs anciens
    log_info "Nettoyage des logs anciens..."
    find "$LOG_DIR" -name "*.log*" -mtime +30 -delete
    
    # Nettoyage des sessions expirées
    log_info "Nettoyage des sessions expirées..."
    python manage.py shell -c "
from sessions.models import WhatsAppSession
from datetime import datetime, timedelta
cutoff = datetime.now() - timedelta(hours=24)
expired = WhatsAppSession.objects.filter(last_activity__lt=cutoff, status='active')
count = expired.count()
expired.update(status='expired')
print(f'Sessions expirées nettoyées: {count}')
"
    
    # Nettoyage des métriques anciennes
    log_info "Nettoyage des métriques anciennes..."
    python manage.py shell -c "
from metrics.models import SystemMetric
from datetime import datetime, timedelta
cutoff = datetime.now() - timedelta(days=30)
old_metrics = SystemMetric.objects.filter(timestamp__lt=cutoff).exclude(metric_type='daily_report')
count = old_metrics.count()
old_metrics.delete()
print(f'Métriques anciennes supprimées: {count}')
"
    
    # Optimisation base de données
    log_info "Optimisation de la base de données..."
    sudo -u postgres psql medirecord_prod -c "VACUUM ANALYZE;" >/dev/null
    
    # Nettoyage Redis
    log_info "Nettoyage du cache Redis..."
    redis-cli FLUSHDB >/dev/null
    
    # Vérification de l'espace disque
    log_info "Vérification de l'espace disque..."
    df -h /
    
    log_info "Maintenance terminée"
}

# 8. MONITOR - Surveillance continue
cmd_monitor() {
    log_step "Mode surveillance MediRecord"
    
    log_info "Surveillance en cours... (Ctrl+C pour arrêter)"
    
    while true; do
        clear
        echo "=== SURVEILLANCE MEDIRECORD - $(date) ==="
        echo ""
        
        # Status services
        echo "🔧 SERVICES:"
        services=("medirecord" "medirecord-celery" "nginx" "postgresql" "redis")
        for service in "${services[@]}"; do
            if systemctl is-active --quiet "$service"; then
                echo -e "  $service: ${GREEN}●${NC}"
            else
                echo -e "  $service: ${RED}●${NC}"
            fi
        done
        
        echo ""
        echo "📊 RESSOURCES:"
        echo "  CPU: $(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1"%"}')"
        echo "  RAM: $(free | grep Mem | awk '{printf "%.1f%%", $3/$2 * 100.0}')"
        echo "  Disk: $(df -h / | awk 'NR==2{print $5}')"
        
        echo ""
        echo "🌐 API:"
        if curl -f -s http://localhost:8000/api/health/ > /dev/null; then
            echo -e "  Health Check: ${GREEN}✓${NC}"
        else
            echo -e "  Health Check: ${RED}✗${NC}"
        fi
        
        echo ""
        echo "📝 LOGS RÉCENTS:"
        echo "  Django: $(tail -n 1 "$LOG_DIR/django.log" 2>/dev/null | cut -c1-80)"
        echo "  Celery: $(tail -n 1 "$LOG_DIR/celery.log" 2>/dev/null | cut -c1-80)"
        
        sleep 5
    done
}

# 9. DOCTOR - Outils pour les médecins
cmd_doctor() {
    log_step "Outils pour les médecins"
    
    activate_venv
    cd "$PROJECT_DIR"
    
    case "$2" in
        "stats")
            log_info "Statistiques des patients:"
            python manage.py shell -c "
from patients.models import Patient
from messaging.models import BroadcastMessage
from datetime import datetime, timedelta

total_patients = Patient.objects.count()
active_patients = Patient.objects.filter(is_active=True).count()
recent_patients = Patient.objects.filter(created_at__gte=datetime.now() - timedelta(days=7)).count()
total_messages = BroadcastMessage.objects.filter(status='sent').count()

print(f'Total patients: {total_patients}')
print(f'Patients actifs: {active_patients}')
print(f'Nouveaux cette semaine: {recent_patients}')
print(f'Messages diffusés envoyés: {total_messages}')
"
            ;;
        "inactive")
            log_info "Patients inactifs (créés mais non activés):"
            python manage.py shell -c "
from patients.models import Patient
from datetime import datetime, timedelta

inactive = Patient.objects.filter(is_active=False, created_at__lt=datetime.now() - timedelta(hours=24))
print(f'Patients inactifs: {inactive.count()}')
for patient in inactive[:10]:
    print(f'  - {patient.full_name()} ({patient.phone}) - créé le {patient.created_at.strftime(\"%d/%m/%Y\")}')
if inactive.count() > 10:
    print(f'  ... et {inactive.count() - 10} autres')
"
            ;;
        "conversations")
            log_info "Conversations récentes:"
            python manage.py shell -c "
from sessions.models import ConversationLog
from datetime import datetime, timedelta

recent = ConversationLog.objects.filter(timestamp__gte=datetime.now() - timedelta(hours=24)).order_by('-timestamp')
print(f'Conversations dernières 24h: {recent.count()}')
for conv in recent[:5]:
    print(f'  - {conv.session.patient.full_name()}: \"{conv.user_message[:50]}...\"')
"
            ;;
        *)
            log_info "Commandes disponibles:"
            echo "  stats        - Statistiques générales"
            echo "  inactive     - Patients inactifs"
            echo "  conversations - Conversations récentes"
            ;;
    esac
}

# 10. RESET - Réinitialisation (DANGER!)
cmd_reset() {
    log_warning "ATTENTION: Cette commande va SUPPRIMER TOUTES LES DONNÉES!"
    log_warning "Cette opération est IRRÉVERSIBLE!"
    echo ""
    read -p "Tapez 'DELETE_ALL_DATA' pour confirmer: " confirm
    
    if [[ "$confirm" != "DELETE_ALL_DATA" ]]; then
        log_info "Réinitialisation annulée"
        exit 0
    fi
    
    log_step "Réinitialisation du système MediRecord"
    
    # Arrêter les services
    systemctl stop medirecord medirecord-celery
    
    activate_venv
    cd "$PROJECT_DIR"
    
    # Supprimer la base de données
    log_info "Suppression de la base de données..."
    sudo -u postgres dropdb medirecord_prod
    sudo -u postgres createdb medirecord_prod
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE medirecord_prod TO medirecord_user;"
    
    # Recréer les tables
    log_info "Recréation des tables..."
    python manage.py migrate
    
    # Supprimer les fichiers media
    log_info "Suppression des fichiers media..."
    rm -rf "$PROJECT_DIR/media/*"
    
    # Vider Redis
    log_info "Vidage du cache Redis..."
    redis-cli FLUSHALL
    
    # Créer un superutilisateur
    log_info "Création d'un superutilisateur..."
    python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superutilisateur créé: admin/admin123')
"
    
    # Redémarrer les services
    systemctl start medirecord medirecord-celery
    
    log_info "Réinitialisation terminée"
    log_warning "Connectez-vous avec: admin/admin123"
}

# Menu d'aide
show_help() {
    echo "Usage: $0 <commande> [options]"
    echo ""
    echo "Commandes disponibles:"
    echo "  status              - Vérifier l'état des services"
    echo "  logs [type]         - Afficher les logs (django|celery|nginx|all)"
    echo "  restart [service]   - Redémarrer les services (django|nginx|all)"
    echo "  backup              - Créer une sauvegarde complète"
    echo "  restore <file>      - Restaurer depuis une sauvegarde"
    echo "  update              - Mettre à jour le système"
    echo "  maintenance         - Opérations de maintenance"
    echo "  monitor             - Surveillance en temps réel"
    echo "  doctor [cmd]        - Outils pour les médecins"
    echo "  reset               - Réinitialisation complète (DANGER!)"
    echo "  help                - Afficher cette aide"
    echo ""
    echo "Exemples:"
    echo "  $0 status"
    echo "  $0 logs django"
    echo "  $0 restart all"
    echo "  $0 backup"
    echo "  $0 doctor stats"
}

# Main
case "$1" in
    "status")
        cmd_status
        ;;
    "logs")
        cmd_logs "$@"
        ;;
    "restart")
        check_permissions "$1"
        cmd_restart "$@"
        ;;
    "backup")
        check_permissions "$1"
        cmd_backup
        ;;
    "restore")
        check_permissions "$1"
        cmd_restore "$@"
        ;;
    "update")
        check_permissions "$1"
        cmd_update
        ;;
    "maintenance")
        check_permissions "$1"
        cmd_maintenance
        ;;
    "monitor")
        cmd_monitor
        ;;
    "doctor")
        cmd_doctor "$@"
        ;;
    "reset")
        check_permissions "$1"
        cmd_reset
        ;;
    "help"|"")
        show_help
        ;;
    *)
        log_error "Commande inconnue: $1"
        show_help
        exit 1
        ;;
esac
