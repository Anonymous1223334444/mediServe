# MediRecord SIS - Documentation Complète

## 📋 Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [Installation et Configuration](#installation-et-configuration)
4. [Guide d'utilisation](#guide-dutilisation)
5. [API Reference](#api-reference)
6. [Workflows N8N](#workflows-n8n)
7. [Déploiement Production](#déploiement-production)
8. [Maintenance et Monitoring](#maintenance-et-monitoring)
9. [Dépannage](#dépannage)
10. [Contribuer](#contribuer)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-mpnet-base-v2')"


---

## 🎯 Vue d'ensemble

MediRecord est un système d'information sanitaire personnalisé qui permet aux professionnels de santé de gérer leurs patients et de fournir un support automatisé via WhatsApp en utilisant l'intelligence artificielle.

### Fonctionnalités Principales

- **Gestion des Patients** : Création, activation et suivi des dossiers patients
- **RAG Conversationnel** : Assistant IA personnalisé basé sur les documents médicaux
- **Messages Diffusés** : Envoi de conseils santé et informations à tous les patients
- **Indexation Automatique** : Traitement et indexation automatique des documents médicaux
- **Interface WhatsApp** : Communication naturelle via WhatsApp
- **Analytics** : Métriques et rapports détaillés

### Technologies Utilisées

- **Backend** : Django 5.2.1 + Django REST Framework
- **Base de données** : PostgreSQL + Redis
- **IA** : Google Gemini pour le LLM et les embeddings
- **Vector Database** : Pinecone pour le stockage des vecteurs
- **Automation** : N8N pour les workflows
- **Messaging** : Twilio WhatsApp API
- **Frontend** : Next.js 14 + Tailwind CSS
- **Task Queue** : Celery + Redis
- **OCR** : Tesseract + Python

---

## 🏗️ Architecture

### Architecture Globale

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Django API    │    │   N8N Workflows│
│   (Next.js)     │◄──►│   (REST API)    │◄──►│   (Automation) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                               │                        │
                               ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   Redis         │    │   Twilio        │
│   (Base données)│    │   (Cache/Queue) │    │   (WhatsApp)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                               │
                               ▼
┌─────────────────┐    ┌─────────────────┐
│   Pinecone      │    │   Google Gemini │
│   (Vecteurs)    │    │   (LLM/Embed)   │
└─────────────────┘    └─────────────────┘
```

### Modules Django

```
mediServe/
├── patients/          # Gestion des patients
├── documents/         # Upload et traitement des documents
├── rag/              # Système RAG (Retrieval-Augmented Generation)
├── messaging/        # Messages diffusés
├── sessions/         # Sessions WhatsApp
├── metrics/          # Métriques et analytics
└── core/            # Utilitaires communs
```

### Flux de Données

1. **Création Patient** : Frontend → Django → N8N → WhatsApp → Patient
2. **Activation** : Patient → WhatsApp → N8N → Django
3. **Indexation Document** : Django → Celery → OCR → Gemini → Pinecone
4. **Conversation RAG** : WhatsApp → N8N → Django → Gemini + Pinecone → WhatsApp
5. **Message Diffusé** : Frontend → Django → N8N → WhatsApp (tous patients)

---

## 🚀 Installation et Configuration

### Prérequis

- Python 3.9+
- Node.js 18+
- PostgreSQL 13+
- Redis 6+
- Docker (optionnel)

### Installation Rapide

```bash
# 1. Cloner le projet
git clone https://github.com/votre-username/medirecord-sis.git
cd medirecord-sis

# 2. Configuration automatique
chmod +x *.sh
make setup

# 3. Configuration des clés API
cp .env.example .env
# Éditez .env avec vos clés

# 4. Installation frontend
make install-frontend

# 5. Démarrage complet
make start
```

### Configuration Manuelle

#### 1. Backend Django

```bash
# Environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Dépendances
pip install -r requirements.txt

# Base de données
python manage.py migrate

# Superutilisateur
python manage.py createsuperuser
```

#### 2. Services Externes

##### Configuration Gemini
```bash
# Obtenir une clé API : https://makersuite.google.com/app/apikey
export GEMINI_API_KEY="votre-clé-gemini"
```

##### Configuration Pinecone
```bash
# Créer un compte : https://www.pinecone.io/
# Créer un index avec dimension 768 et métrique cosine
export PINECONE_API_KEY="votre-clé-pinecone"
export PINECONE_INDEX_NAME="medirecord-rag"
```

##### Configuration Twilio
```bash
# Console Twilio : https://console.twilio.com/
export TWILIO_ACCOUNT_SID="votre-sid"
export TWILIO_AUTH_TOKEN="votre-token"
export TWILIO_WHATSAPP_NUMBER="+14155238886"  # Sandbox
```

#### 3. Frontend Next.js

```bash
# Installation dépendances
npm install

# Configuration
echo "NEXT_PUBLIC_DJANGO_API_BASE_URL=http://localhost:8000" > .env.local

# Démarrage
npm run dev
```

---

## 📖 Guide d'utilisation

### Interface Médecin

#### 1. Créer un Patient

1. Accédez à `/dashboard/patients/new`
2. Remplissez le formulaire patient
3. Uploadez les documents médicaux (PDF, images)
4. Cliquez sur "Créer le patient"
5. Le patient reçoit automatiquement un message WhatsApp d'activation

#### 2. Envoyer un Message Diffusé

1. Accédez à `/dashboard/messages`
2. Cliquez sur "Nouveau Message"
3. Rédigez votre message
4. Choisissez les critères de ciblage (optionnel)
5. Envoyez immédiatement ou programmez

### Interface Patient (WhatsApp)

#### 1. Activation du Compte

1. Le patient reçoit un message avec un lien d'activation
2. Il clique sur le lien qui ouvre WhatsApp
3. Il envoie le message de confirmation demandé
4. Son compte est activé automatiquement

#### 2. Conversations avec l'IA

```
Patient: "Quelle est ma dernière ordonnance ?"
IA: "Selon votre dossier médical, votre dernière ordonnance 
     du Dr. Martin du 15/11/2024 contient :
     - Lisinopril 10mg, 1 comprimé par jour
     - Aspirine 75mg, 1 comprimé par jour
     
     N'hésitez pas si vous avez des questions !"
```

### Analytics et Métriques

Accédez aux métriques via `/api/metrics/dashboard/` :

- Temps de réponse moyen
- Taux de succès d'indexation
- Engagement des messages
- Santé des services

---

## 🔌 API Reference

### Patients

#### Créer un Patient
```http
POST /api/patients/
Content-Type: application/json

{
    "first_name": "Jean",
    "last_name": "Dupont",
    "email": "jean@example.com",
    "phone": "+221771234567",
    "date_of_birth": "1980-01-01",
    "gender": "M",
    "address": "123 Rue Test",
    "medical_history": "Hypertension",
    "allergies": "Pénicilline",
    "current_medications": "Lisinopril"
}
```

#### Confirmer Activation
```http
POST /api/patients/confirm/
Content-Type: application/json

{
    "phone": "+221771234567",
    "valid": true
}
```

#### Vérifier Statut
```http
POST /api/patients/check-active/
Content-Type: application/json

{
    "phone": "+221771234567"
}
```

### RAG (Retrieval-Augmented Generation)

#### Requête RAG
```http
POST /api/rag/query/
Content-Type: application/json

{
    "patient_phone": "+221771234567",
    "query": "Quelle est ma posologie ?",
    "session_id": "whatsapp_221771234567_20241201"
}
```

### Messages Diffusés

#### Créer un Message
```http
POST /api/messaging/broadcast/
Content-Type: application/json

{
    "title": "Conseil nutrition",
    "content": "Mangez 5 fruits et légumes par jour",
    "category": "health_tip",
    "target_all_patients": true
}
```

#### Envoyer Immédiatement
```http
POST /api/messaging/broadcast/{id}/send_now/
```

### Documents

#### Upload Document
```http
POST /api/documents/
Content-Type: multipart/form-data

patient_id: 123
file: [fichier PDF ou image]
```

### Métriques

#### Dashboard Métriques
```http
GET /api/metrics/dashboard/?hours=24
```

#### Health Check
```http
GET /api/health/
```

---

## 🤖 Workflows N8N

### 1. Workflow d'Activation Patient

**Déclencheur** : Webhook `/webhook/confirm-{token}`

**Étapes** :
1. Réception message WhatsApp
2. Vérification du message de confirmation
3. Appel API Django pour activer le patient
4. Notification au médecin

### 2. Workflow RAG Conversationnel

**Déclencheur** : Webhook `/whatsapp-rag`

**Étapes** :
1. Extraction données WhatsApp
2. Vérification patient actif
3. Appel API RAG Django
4. Réponse WhatsApp au patient
5. Log de la conversation

### 3. Workflow Messages Diffusés

**Déclencheur** : Webhook `/broadcast-message`

**Étapes** :
1. Réception données du message
2. Division par patient cible
3. Envoi WhatsApp avec délai
4. Log du statut de livraison
5. Rapport final

### Configuration des Credentials N8N

1. **Twilio** :
   - User: Account SID
   - Password: Auth Token

2. **Django API** :
   - Utiliser les URLs de base configurées

---

## 🌐 Déploiement Production

### 1. Serveur Cloud (Ubuntu 22.04)

#### Installation des Dépendances
```bash
# Mise à jour système
sudo apt update && sudo apt upgrade -y

# Python et outils
sudo apt install -y python3.11 python3.11-venv python3-pip
sudo apt install -y postgresql postgresql-contrib redis-server
sudo apt install -y nginx certbot python3-certbot-nginx
sudo apt install -y tesseract-ocr tesseract-ocr-fra

# Docker pour N8N
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

#### Configuration Base de Données
```bash
sudo -u postgres createdb medirecord_prod
sudo -u postgres createuser medirecord_user
sudo -u postgres psql -c "ALTER USER medirecord_user WITH PASSWORD 'mot_de_passe_securise';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE medirecord_prod TO medirecord_user;"
```

### 2. Configuration Django Production

#### settings_production.py
```python
import os
from .settings import *

DEBUG = False
ALLOWED_HOSTS = ['votre-domaine.com', 'www.votre-domaine.com']

# Base de données
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'medirecord_prod',
        'USER': 'medirecord_user',
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Sécurité
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# HTTPS
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Logs
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/medirecord/django.log',
            'maxBytes': 50*1024*1024,  # 50MB
            'backupCount': 5,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'medirecord': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### 3. Gunicorn et Systemd

#### /etc/systemd/system/medirecord.service
```ini
[Unit]
Description=MediRecord Django
After=network.target

[Service]
User=medirecord
Group=www-data
WorkingDirectory=/home/medirecord/medirecord-sis
Environment="PATH=/home/medirecord/medirecord-sis/venv/bin"
ExecStart=/home/medirecord/medirecord-sis/venv/bin/gunicorn \
          --workers 3 \
          --bind unix:/home/medirecord/medirecord-sis/medirecord.sock \
          --access-logfile /var/log/medirecord/access.log \
          --error-logfile /var/log/medirecord/error.log \
          mediServe.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

#### /etc/systemd/system/medirecord-celery.service
```ini
[Unit]
Description=MediRecord Celery Worker
After=network.target

[Service]
User=medirecord
Group=www-data
WorkingDirectory=/home/medirecord/medirecord-sis
Environment="PATH=/home/medirecord/medirecord-sis/venv/bin"
ExecStart=/home/medirecord/medirecord-sis/venv/bin/celery \
          -A mediServe worker \
          --loglevel=info \
          --logfile=/var/log/medirecord/celery.log
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4. Configuration Nginx

#### /etc/nginx/sites-available/medirecord
```nginx
server {
    listen 80;
    server_name votre-domaine.com www.votre-domaine.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name votre-domaine.com www.votre-domaine.com;

    ssl_certificate /etc/letsencrypt/live/votre-domaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/votre-domaine.com/privkey.pem;

    client_max_body_size 100M;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /home/medirecord/medirecord-sis;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        root /home/medirecord/medirecord-sis;
        expires 7d;
        add_header Cache-Control "public";
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/medirecord/medirecord-sis/medirecord.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Sécurité
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
}
```

### 5. Déploiement N8N Production

#### docker-compose.yml
```yaml
version: '3.8'

services:
  n8n:
    image: docker.n8n.io/n8nio/n8n
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_HOST=n8n.votre-domaine.com
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - NODE_ENV=production
      - WEBHOOK_URL=https://n8n.votre-domaine.com/
      - GENERIC_TIMEZONE=UTC
      - N8N_LOG_LEVEL=info
    volumes:
      - n8n_data:/home/node/.n8n
      - /var/run/docker.sock:/var/run/docker.sock

volumes:
  n8n_data:
```

### 6. Certificats SSL

```bash
# Certificats Let's Encrypt
sudo certbot --nginx -d votre-domaine.com -d www.votre-domaine.com
sudo certbot --nginx -d n8n.votre-domaine.com

# Renouvellement automatique
sudo crontab -e
# Ajouter: 0 12 * * * /usr/bin/certbot renew --quiet
```

### 7. Monitoring et Backups

#### Script de Backup
```bash
#!/bin/bash
# /home/medirecord/scripts/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/medirecord"

# Backup base de données
pg_dump -h localhost -U medirecord_user medirecord_prod > "$BACKUP_DIR/db_$DATE.sql"

# Backup fichiers
tar -czf "$BACKUP_DIR/media_$DATE.tar.gz" /home/medirecord/medirecord-sis/media/

# Backup N8N
docker exec -t n8n_container n8n export:workflow --backup --output=/home/node/.n8n/backups/workflows_$DATE.json

# Nettoyage (garder 30 jours)
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

#### Crontab pour Backup Quotidien
```bash
0 2 * * * /home/medirecord/scripts/backup.sh >> /var/log/medirecord/backup.log 2>&1
```

---

## 📊 Maintenance et Monitoring

### 1. Logs à Surveiller

```bash
# Logs Django
tail -f /var/log/medirecord/django.log

# Logs Celery
tail -f /var/log/medirecord/celery.log

# Logs Nginx
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Logs PostgreSQL
sudo tail -f /var/log/postgresql/postgresql-14-main.log
```

### 2. Commandes de Maintenance

#### Nettoyage Base de Données
```bash
# Supprimer anciennes métriques
python manage.py shell -c "
from metrics.models import SystemMetric
from datetime import datetime, timedelta
cutoff = datetime.now() - timedelta(days=30)
SystemMetric.objects.filter(timestamp__lt=cutoff).delete()
"

# Nettoyer sessions expirées
python manage.py shell -c "
from sessions.models import WhatsAppSession
from datetime import datetime, timedelta
cutoff = datetime.now() - timedelta(hours=24)
WhatsAppSession.objects.filter(last_activity__lt=cutoff).update(status='expired')
"
```

#### Optimisation Base de Données
```bash
# Vacuum PostgreSQL
sudo -u postgres psql medirecord_prod -c "VACUUM ANALYZE;"

# Reindex
sudo -u postgres psql medirecord_prod -c "REINDEX DATABASE medirecord_prod;"
```

### 3. Monitoring Automatique

#### Script de Health Check
```bash
#!/bin/bash
# /home/medirecord/scripts/health_check.sh

# Vérifier services
systemctl is-active --quiet medirecord || echo "ALERTE: Django service down"
systemctl is-active --quiet medirecord-celery || echo "ALERTE: Celery service down"
systemctl is-active --quiet nginx || echo "ALERTE: Nginx service down"
systemctl is-active --quiet postgresql || echo "ALERTE: PostgreSQL service down"
systemctl is-active --quiet redis || echo "ALERTE: Redis service down"

# Vérifier API
curl -f -s http://localhost:8000/api/health/ || echo "ALERTE: Health check API failed"

# Vérifier espace disque
df -h / | awk 'NR==2 {if($5+0 > 85) print "ALERTE: Disk usage " $5}'

# Vérifier mémoire
free | awk 'NR==2{printf "Memory: %.0f%%\n", $3/$2*100}' | awk '{if($2+0 > 90) print "ALERTE: " $0}'
```

### 4. Alertes Email

#### Configuration Email Django
```python
# settings_production.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_PASSWORD')
DEFAULT_FROM_EMAIL = 'noreply@votre-domaine.com'

ADMINS = [
    ('Admin', 'admin@votre-domaine.com'),
]
```

---

## 🔧 Dépannage

### Problèmes Courants

#### 1. Erreur de Connexion Pinecone
```python
# Vérifier la configuration
python manage.py shell
>>> from rag.services import PineconeService
>>> service = PineconeService()
>>> print(service.index.describe_index_stats())
```

#### 2. Messages WhatsApp Non Reçus
```bash
# Vérifier logs Twilio
curl -X GET "https://api.twilio.com/2010-04-01/Accounts/$TWILIO_ACCOUNT_SID/Messages.json" \
     -u "$TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN"

# Vérifier webhook N8N
curl -X POST https://votre-n8n.com/webhook/test \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}'
```

#### 3. Workflows N8N Inactifs
1. Vérifier que les workflows sont activés
2. Contrôler les credentials Twilio
3. Vérifier les URLs de webhook
4. Consulter les logs d'exécution

#### 4. Performance Lente
```bash
# Vérifier utilisation CPU/Mémoire
htop

# Vérifier connexions base de données
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"

# Vérifier Redis
redis-cli info stats
```

### Codes d'Erreur API

| Code | Signification | Solution |
|------|---------------|----------|
| 400 | Données invalides | Vérifier le format des données envoyées |
| 401 | Non autorisé | Vérifier les tokens d'authentification |
| 404 | Patient non trouvé | Vérifier que le patient existe et est actif |
| 500 | Erreur serveur | Consulter les logs Django |
| 503 | Service indisponible | Vérifier les services externes (Pinecone, Gemini) |

---

## 🤝 Contribuer

### Structure du Code

```
mediServe/
├── patients/          # Module patients
│   ├── models.py      # Modèles de données
│   ├── views.py       # Vues API
│   ├── serializers.py # Sérialiseurs DRF
│   ├── tasks.py       # Tâches Celery
│   └── n8n_manager.py # Interface N8N
├── rag/              # Module RAG
│   ├── models.py     # Modèles documents/conversations
│   ├── services.py   # Services IA (Gemini, Pinecone)
│   └── views.py      # API RAG
├── messaging/        # Module messages diffusés
│   ├── models.py     # Modèles broadcast
│   ├── views.py      # API messaging
│   ├── tasks.py      # Envoi asynchrone
│   └── services.py   # Service WhatsApp
└── tests/           # Tests automatisés
```

### Standards de Code

- **Python** : PEP 8 + Black formatter
- **JavaScript** : ESLint + Prettier
- **Tests** : Pytest pour Python, Jest pour Frontend
- **Documentation** : Docstrings pour toutes les fonctions publiques

### Process de Contribution

1. Fork le repository
2. Créer une branche feature (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commiter les changements (`git commit -am 'Ajouter nouvelle fonctionnalité'`)
4. Pousser vers la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. Créer une Pull Request

### Tests Requis

```bash
# Tests unitaires
make test

# Tests de couverture
make test-coverage

# Tests d'intégration
make test-integration

# Vérification du code
make lint
```

---

## 📞 Support

- **Documentation** : Cette documentation
- **Issues** : GitHub Issues pour les bugs
- **Email** : support@votre-domaine.com
- **Discord** : Serveur communauté (optionnel)

---

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

---

## 🔄 Changelog

### v1.0.0 (2024-12-01)
- Implémentation initiale du système RAG
- Interface patient WhatsApp
- Messages diffusés
- Dashboard médecin
- Monitoring et métriques

### v1.1.0 (Planifié)
- Support vocal en Wolof
- Interface mobile native
- Analytics avancés
- Intégration FHIR

---

## 🙏 Remerciements

- Équipe de développement
- Professionnels de santé testeurs
- Communauté open source
- Google (Gemini API)
- Pinecone
- Twilio
- N8N Community