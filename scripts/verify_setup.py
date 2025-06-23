#!/usr/bin/env python3
"""
Script pour vérifier la configuration de base du projet
"""
import os
import sys

print("🔍 === VÉRIFICATION DE LA CONFIGURATION ===\n")

# 1. Vérifier le répertoire actuel
print("📁 Répertoire d'exécution:")
print(f"   Actuel: {os.getcwd()}")

# 2. Vérifier la structure du projet
required_files = ['manage.py', 'mediServe/__init__.py', 'requirements.txt']
project_root = None

# Chercher la racine du projet
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

if all(os.path.exists(os.path.join(parent_dir, f)) for f in required_files):
    project_root = parent_dir
    print(f"   Racine du projet: {project_root}")
else:
    print("❌ Structure du projet non trouvée!")
    print("   Fichiers recherchés:", required_files)
    sys.exit(1)

# 3. Configurer le PYTHONPATH
sys.path.insert(0, project_root)
print(f"\n🐍 PYTHONPATH configuré:")
print(f"   {project_root}")

# 4. Vérifier les variables d'environnement
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')
print(f"\n🔧 Variables d'environnement:")
print(f"   DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE')}")

# 5. Tester l'import Django
print("\n📦 Test des imports:")
try:
    import django
    print(f"   ✅ Django {django.__version__}")
    
    # Configurer Django
    django.setup()
    print("   ✅ Django configuré avec succès")
    
    # Tester l'accès aux settings
    from django.conf import settings
    print(f"   ✅ BASE_DIR: {settings.BASE_DIR}")
    print(f"   ✅ DEBUG: {settings.DEBUG}")
    
except Exception as e:
    print(f"   ❌ Erreur Django: {type(e).__name__}: {e}")
    sys.exit(1)

# 6. Tester les imports du projet
print("\n📚 Test des modules du projet:")
modules_to_test = [
    'patients.models',
    'documents.models',
    'documents.tasks',
    'messaging.services',
]

for module in modules_to_test:
    try:
        __import__(module)
        print(f"   ✅ {module}")
    except ImportError as e:
        print(f"   ❌ {module}: {e}")

# 7. Vérifier Redis
print("\n🔴 Test Redis:")
try:
    import redis
    r = redis.from_url(settings.CELERY_BROKER_URL)
    if r.ping():
        print(f"   ✅ Redis connecté: {settings.CELERY_BROKER_URL}")
    else:
        print(f"   ❌ Redis ne répond pas")
except Exception as e:
    print(f"   ❌ Erreur Redis: {e}")

# 8. Vérifier Celery
print("\n🌿 Test Celery:")
try:
    from celery import current_app
    print(f"   ✅ Celery app: {current_app.main}")
    
    # Lister les tâches
    tasks = [t for t in current_app.tasks if not t.startswith('celery.')]
    print(f"   📋 {len(tasks)} tâches enregistrées:")
    for task in tasks[:5]:  # Afficher les 5 premières
        print(f"      - {task}")
    if len(tasks) > 5:
        print(f"      ... et {len(tasks) - 5} autres")
        
except Exception as e:
    print(f"   ❌ Erreur Celery: {e}")

# 9. Vérifier les répertoires
print("\n📂 Vérification des répertoires:")
dirs_to_check = [
    'media',
    'media/patient_documents',
    'media/vectors',
    'media/indexes',
    'logs',
    'scripts'
]

for dir_path in dirs_to_check:
    full_path = os.path.join(project_root, dir_path)
    if os.path.exists(full_path):
        print(f"   ✅ {dir_path}")
    else:
        print(f"   ❌ {dir_path} (manquant)")

# 10. Vérifier le fichier .env
print("\n🔐 Fichier .env:")
env_path = os.path.join(project_root, '.env')
if os.path.exists(env_path):
    print(f"   ✅ Fichier .env trouvé")
    # Vérifier quelques variables clés
    from dotenv import load_dotenv
    load_dotenv(env_path)
    
    env_vars = [
        'DJANGO_SECRET_KEY',
        'CELERY_BROKER_URL',
        'TWILIO_ACCOUNT_SID',
        'GEMINI_API_KEY'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value and value != f'your-{var.lower()}':
            print(f"   ✅ {var}: configuré")
        else:
            print(f"   ⚠️  {var}: non configuré")
else:
    print(f"   ❌ Fichier .env non trouvé")

print("\n✅ Vérification terminée!")
print("\n📋 Pour exécuter les tests:")
print(f"   cd {project_root}")
print("   python scripts/test_celery_vectorization.py celery")