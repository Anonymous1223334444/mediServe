MONITOR_DIR="/var/log/medirecord/monitoring"
ALERT_EMAIL="admin@votre-domaine.com"
WEBHOOK_URL="" # Slack/Discord webhook optionnel

mkdir -p "$MONITOR_DIR"

# Fonction d'alerte
send_alert() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo "[$timestamp] [$level] $message" >> "$MONITOR_DIR/alerts.log"
    
    # Email
    if command -v mail &> /dev/null; then
        echo "$message" | mail -s "MediRecord Alert [$level]" "$ALERT_EMAIL"
    fi
    
    # Webhook (Slack/Discord)
    if [[ -n "$WEBHOOK_URL" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data '{"text":"[MediRecord]['$level'] '$message'"}' \
            "$WEBHOOK_URL" &>/dev/null
    fi
}

# Vérifications système
check_services() {
    local failed_services=()
    
    for service in medirecord medirecord-celery nginx postgresql redis; do
        if ! systemctl is-active --quiet "$service"; then
            failed_services+=("$service")
        fi
    done
    
    if [[ ${#failed_services[@]} -gt 0 ]]; then
        send_alert "CRITICAL" "Services en panne: ${failed_services[*]}"
    fi
}

check_resources() {
    # CPU
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        send_alert "WARNING" "CPU usage élevé: ${cpu_usage}%"
    fi
    
    # RAM
    ram_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$ram_usage > 85" | bc -l) )); then
        send_alert "WARNING" "RAM usage élevé: ${ram_usage}%"
    fi
    
    # Disk
    disk_usage=$(df -h / | awk 'NR==2{print $5}' | sed 's/%//')
    if [[ $disk_usage -gt 85 ]]; then
        send_alert "WARNING" "Disque plein: ${disk_usage}%"
    fi
}

check_api() {
    if ! curl -f -s http://localhost:8000/api/health/ >/dev/null; then
        send_alert "CRITICAL" "API Health Check échoué"
    fi
}

check_database() {
    local connections=$(sudo -u postgres psql medirecord_prod -t -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null | tr -d ' ')
    if [[ $connections -gt 50 ]]; then
        send_alert "WARNING" "Trop de connexions DB: $connections"
    fi
}

# Exécution des vérifications
check_services
check_resources
check_api
check_database

# Enregistrer les métriques
echo "$(date '+%Y-%m-%d %H:%M:%S'),$(cat /proc/loadavg | cut -d' ' -f1),$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')" >> "$MONITOR_DIR/metrics.csv"
