#!/usr/bin/env python3
"""
Script pour vérifier l'état de Redis et Celery
"""
import os
import sys
import redis
import json

def check_redis_connection():
    """Vérifier la connexion Redis"""
    print("=== VÉRIFICATION REDIS ===")
    
    # Essayer différentes URLs Redis communes
    redis_urls = [
        'redis://localhost:6379/0',
        'redis://127.0.0.1:6379/0',
        'redis://redis:6379/0',  # Docker
        os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    ]
    
    for url in redis_urls:
        try:
            print(f"\nTest de connexion: {url}")
            r = redis.from_url(url)
            
            # Test ping
            if r.ping():
                print(f"✅ Connexion réussie!")
                
                # Informations sur Redis
                info = r.info()
                print(f"   Version Redis: {info.get('redis_version', 'unknown')}")
                print(f"   Clients connectés: {info.get('connected_clients', 0)}")
                print(f"   Mémoire utilisée: {info.get('used_memory_human', 'unknown')}")
                
                # Vérifier les clés Celery
                celery_keys = []
                for key in r.scan_iter("celery*"):
                    celery_keys.append(key.decode('utf-8'))
                
                print(f"   Clés Celery trouvées: {len(celery_keys)}")
                if celery_keys:
                    print("   Exemples de clés:")
                    for key in celery_keys[:5]:
                        print(f"     - {key}")
                
                # Vérifier les tâches en attente
                queues = ['celery', 'default', 'high_priority', 'messaging', 'maintenance']
                for queue in queues:
                    queue_key = f"celery:queue:{queue}"
                    queue_length = r.llen(queue_key)
                    if queue_length > 0:
                        print(f"   Queue '{queue}': {queue_length} tâches")
                
                return True
                
        except redis.ConnectionError as e:
            print(f"❌ Échec de connexion: {e}")
        except Exception as e:
            print(f"❌ Erreur: {type(e).__name__}: {e}")
    
    return False

def check_celery_workers():
    """Vérifier les workers Celery actifs"""
    print("\n=== VÉRIFICATION WORKERS CELERY ===")
    
    try:
        from celery import Celery
        app = Celery('mediServe')
        app.config_from_object('django.conf:settings', namespace='CELERY')
        
        # Inspecter les workers
        i = app.control.inspect()
        
        # Workers actifs
        active_workers = i.active()
        if active_workers:
            print(f"✅ {len(active_workers)} worker(s) actif(s):")
            for worker, tasks in active_workers.items():
                print(f"   - {worker}: {len(tasks)} tâche(s) active(s)")
        else:
            print("❌ Aucun worker actif trouvé!")
            print("   Assurez-vous que Celery est lancé avec:")
            print("   celery -A mediServe worker -l info")
        
        # Tâches enregistrées
        registered = i.registered()
        if registered:
            print(f"\n📋 Tâches enregistrées:")
            for worker, tasks in registered.items():
                print(f"   Worker: {worker}")
                for task in sorted(tasks):
                    if not task.startswith('celery.'):
                        print(f"     - {task}")
        
        # Statistiques
        stats = i.stats()
        if stats:
            print(f"\n📊 Statistiques:")
            for worker, stat in stats.items():
                print(f"   Worker: {worker}")
                print(f"     - Pool: {stat.get('pool', {}).get('max-concurrency', 'unknown')} threads")
                
    except Exception as e:
        print(f"❌ Erreur inspection Celery: {type(e).__name__}: {e}")
        print("   Celery n'est probablement pas en cours d'exécution")

def suggest_fixes():
    """Suggérer des corrections"""
    print("\n=== SUGGESTIONS DE CORRECTION ===")
    
    print("\n1. Vérifier que Redis est installé et lancé:")
    print("   sudo apt-get install redis-server")
    print("   sudo systemctl start redis")
    print("   sudo systemctl status redis")
    
    print("\n2. Lancer Celery avec plus de logs:")
    print("   celery -A mediServe worker -l debug --pool=solo")
    
    print("\n3. Vérifier les variables d'environnement dans .env:")
    print("   CELERY_BROKER_URL=redis://localhost:6379/0")
    print("   CELERY_RESULT_BACKEND=redis://localhost:6379/0")
    
    print("\n4. Tester la tâche de debug:")
    print("   python manage.py shell")
    print("   >>> from mediServe.celery import debug_task")
    print("   >>> result = debug_task.delay()")
    print("   >>> print(result.id)")

def main():
    # Configurer Django si nécessaire
    if 'DJANGO_SETTINGS_MODULE' not in os.environ:
        # Ajouter le répertoire parent au PYTHONPATH
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        sys.path.insert(0, parent_dir)
        
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')
        
        try:
            import django
            django.setup()
        except Exception as e:
            print(f"⚠️  Impossible de configurer Django: {e}")
            print(f"    Répertoire actuel: {os.getcwd()}")
            print(f"    PYTHONPATH: {sys.path[:3]}")
    
    print("🔍 Diagnostic du système Celery/Redis\n")
    
    redis_ok = check_redis_connection()
    
    if redis_ok:
        check_celery_workers()
    
    suggest_fixes()

if __name__ == "__main__":
    main()