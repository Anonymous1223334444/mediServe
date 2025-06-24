# scripts/cleanup_all_data.py
"""
Script pour supprimer toutes les données (patients, documents, médias)
tout en gardant la structure de la base de données
"""
import os
import sys
import shutil
import django
from django.db import connection

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')
django.setup()

from django.conf import settings
from patients.models import Patient
from documents.models import DocumentUpload
from rag.models import Document, ConversationSession, Message
from sessions.models import WhatsAppSession, ConversationLog
from metrics.models import SystemMetric, PerformanceAlert

def colored_print(message, color='green'):
    """Affiche un message coloré"""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'reset': '\033[0m'
    }
    print(f"{colors.get(color, '')}{message}{colors['reset']}")

def confirm_action():
    """Demande confirmation avant de procéder"""
    colored_print("\n⚠️  ATTENTION: Cette action va supprimer:", 'red')
    colored_print("   - Tous les patients", 'yellow')
    colored_print("   - Tous les documents uploadés", 'yellow')
    colored_print("   - Tous les fichiers médias", 'yellow')
    colored_print("   - Toutes les conversations", 'yellow')
    colored_print("   - Toutes les métriques", 'yellow')
    colored_print("   - Tous les vector stores", 'yellow')
    
    colored_print("\n✅ La structure de la base de données sera préservée", 'green')
    
    response = input("\n🔴 Êtes-vous sûr de vouloir continuer? (tapez 'OUI' pour confirmer): ")
    return response == "OUI"

def clean_media_files():
    """Supprime tous les fichiers médias"""
    colored_print("\n🗑️  Nettoyage des fichiers médias...", 'blue')
    
    media_dirs = [
        'patient_documents',
        'documents',
        'vectors',
        'indexes',
        'temp'
    ]
    
    for dir_name in media_dirs:
        dir_path = os.path.join(settings.MEDIA_ROOT, dir_name)
        if os.path.exists(dir_path):
            try:
                # Compter les fichiers avant suppression
                file_count = sum([len(files) for r, d, files in os.walk(dir_path)])
                
                # Supprimer le contenu mais garder le dossier
                for filename in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, filename)
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                
                colored_print(f"   ✅ {dir_name}: {file_count} fichiers supprimés", 'green')
            except Exception as e:
                colored_print(f"   ❌ Erreur {dir_name}: {e}", 'red')
        else:
            colored_print(f"   ⚠️  {dir_name}: dossier inexistant", 'yellow')

def clean_database_data():
    """Supprime toutes les données de la base"""
    colored_print("\n🗑️  Nettoyage de la base de données...", 'blue')
    
    # Ordre de suppression important (à cause des foreign keys)
    models_to_clean = [
        # D'abord les modèles dépendants
        ('Message', Message),
        ('ConversationSession', ConversationSession),
        ('ConversationLog', ConversationLog),
        ('WhatsAppSession', WhatsAppSession),
        ('Document', Document),
        ('DocumentUpload', DocumentUpload),
        ('SystemMetric', SystemMetric),
        ('PerformanceAlert', PerformanceAlert),
        # Enfin le modèle principal
        ('Patient', Patient),
    ]
    
    for model_name, model_class in models_to_clean:
        try:
            count = model_class.objects.count()
            if count > 0:
                model_class.objects.all().delete()
                colored_print(f"   ✅ {model_name}: {count} enregistrements supprimés", 'green')
            else:
                colored_print(f"   ⚠️  {model_name}: déjà vide", 'yellow')
        except Exception as e:
            colored_print(f"   ❌ Erreur {model_name}: {e}", 'red')

def reset_sequences():
    """Réinitialise les séquences/auto-increment pour PostgreSQL"""
    colored_print("\n🔧 Réinitialisation des séquences...", 'blue')
    
    with connection.cursor() as cursor:
        # Tables à réinitialiser
        tables = [
            'patients_patient',
            'documents_documentupload',
            'rag_document',
            'rag_conversationsession',
            'rag_message',
            'sessions_whatsappsession',
            'sessions_conversationlog',
            'metrics_systemmetric',
            'metrics_performancealert'
        ]
        
        for table in tables:
            try:
                # Pour PostgreSQL
                cursor.execute(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table}', 'id'),
                        1,
                        false
                    );
                """)
                colored_print(f"   ✅ Séquence réinitialisée: {table}", 'green')
            except Exception as e:
                # Si la table n'existe pas ou autre erreur
                colored_print(f"   ⚠️  {table}: {e}", 'yellow')

def clean_redis():
    """Nettoie Redis (Celery tasks)"""
    colored_print("\n🗑️  Nettoyage de Redis...", 'blue')
    
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        
        # Nettoyer les queues Celery
        celery_keys = r.keys('celery*')
        if celery_keys:
            r.delete(*celery_keys)
            colored_print(f"   ✅ {len(celery_keys)} clés Celery supprimées", 'green')
        else:
            colored_print("   ⚠️  Aucune clé Celery trouvée", 'yellow')
            
    except Exception as e:
        colored_print(f"   ❌ Erreur Redis: {e}", 'red')

def recreate_directories():
    """Recrée les dossiers nécessaires"""
    colored_print("\n📁 Recréation des dossiers...", 'blue')
    
    directories = [
        os.path.join(settings.MEDIA_ROOT, 'patient_documents'),
        os.path.join(settings.MEDIA_ROOT, 'documents'),
        os.path.join(settings.MEDIA_ROOT, 'vectors'),
        os.path.join(settings.MEDIA_ROOT, 'indexes'),
        os.path.join(settings.MEDIA_ROOT, 'temp'),
        os.path.join(settings.BASE_DIR, 'logs'),
    ]
    
    for dir_path in directories:
        os.makedirs(dir_path, exist_ok=True)
        colored_print(f"   ✅ {os.path.basename(dir_path)}", 'green')

def show_final_status():
    """Affiche le statut final"""
    colored_print("\n📊 STATUT FINAL", 'blue')
    colored_print("=" * 50, 'blue')
    
    # Vérifier que tout est vide
    checks = [
        ('Patients', Patient.objects.count()),
        ('Documents', DocumentUpload.objects.count()),
        ('RAG Documents', Document.objects.count()),
        ('Sessions WhatsApp', WhatsAppSession.objects.count()),
        ('Métriques', SystemMetric.objects.count()),
    ]
    
    all_empty = True
    for name, count in checks:
        if count == 0:
            colored_print(f"✅ {name}: {count}", 'green')
        else:
            colored_print(f"❌ {name}: {count} (devrait être 0)", 'red')
            all_empty = False
    
    # Vérifier les fichiers
    media_files = 0
    for root, dirs, files in os.walk(settings.MEDIA_ROOT):
        media_files += len(files)
    
    if media_files == 0:
        colored_print(f"✅ Fichiers médias: {media_files}", 'green')
    else:
        colored_print(f"⚠️  Fichiers médias restants: {media_files}", 'yellow')
    
    if all_empty and media_files == 0:
        colored_print("\n🎉 Base de données complètement nettoyée!", 'green')
        colored_print("   Vous pouvez maintenant repartir de zéro.", 'green')
    else:
        colored_print("\n⚠️  Certains éléments n'ont pas pu être supprimés", 'yellow')

def main():
    """Fonction principale"""
    colored_print("🧹 SCRIPT DE NETTOYAGE COMPLET", 'blue')
    colored_print("=" * 50, 'blue')
    
    # Demander confirmation
    if not confirm_action():
        colored_print("\n❌ Opération annulée", 'red')
        return
    
    colored_print("\n🚀 Démarrage du nettoyage...", 'blue')
    
    try:
        # 1. Nettoyer les fichiers médias
        clean_media_files()
        
        # 2. Nettoyer la base de données
        clean_database_data()
        
        # 3. Réinitialiser les séquences
        reset_sequences()
        
        # 4. Nettoyer Redis
        clean_redis()
        
        # 5. Recréer les dossiers
        recreate_directories()
        
        # 6. Afficher le statut final
        show_final_status()
        
    except Exception as e:
        colored_print(f"\n❌ Erreur critique: {e}", 'red')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()