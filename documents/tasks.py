from celery import shared_task
from django.utils import timezone
from .models import DocumentUpload
from rag.models import Document
from rag.services import RAGService
import logging
import os
import shutil
from celery import shared_task
from django.db.models import Avg, Count, Sum
from datetime import datetime, timedelta
from metrics.models import SystemMetric, PerformanceAlert
from metrics.services import MetricsService
import psutil
import logging


logger = logging.getLogger(__name__)

@shared_task
def process_document_async(document_upload_id):
    """
    Tâche Celery pour traiter un document uploadé:
    1. Valider le fichier
    2. Créer l'entrée Document pour RAG
    3. Indexer dans Pinecone
    """
    try:
        doc_upload = DocumentUpload.objects.get(id=document_upload_id)
        doc_upload.upload_status = 'processing'
        doc_upload.save()
        
        # 1. Valider le type de fichier
        allowed_types = ['pdf', 'jpg', 'jpeg', 'png', 'tiff']
        if doc_upload.file_type.lower() not in allowed_types:
            raise ValueError(f"Type de fichier non supporté: {doc_upload.file_type}")
        
        # 2. Copier le fichier vers le dossier de stockage permanent
        file_path = _copy_to_permanent_storage(doc_upload)
        
        # 3. Créer l'entrée Document pour RAG
        rag_document = Document.objects.create(
            patient=doc_upload.patient,
            file_name=doc_upload.original_filename,
            file_path=file_path,
            file_type='pdf' if doc_upload.file_type.lower() == 'pdf' else 'image'
        )
        
        # 4. Indexer le document
        rag_service = RAGService()
        success = rag_service.index_document(rag_document)
        
        if success:
            doc_upload.upload_status = 'indexed'
            doc_upload.processed_at = timezone.now()
            logger.info(f"Document {doc_upload.id} indexé avec succès")
        else:
            raise Exception("Échec de l'indexation dans Pinecone")
            
    except Exception as e:
        logger.error(f"Erreur traitement document {document_upload_id}: {e}")
        doc_upload.upload_status = 'failed'
        doc_upload.error_message = str(e)
    
    finally:
        doc_upload.save()

@shared_task
def collect_system_metrics():
    """Collecte les métriques système (CPU, mémoire, etc.)"""
    try:
        # Métriques système
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Enregistrer les métriques
        SystemMetric.objects.create(
            metric_type='system_cpu',
            value=cpu_percent,
            metadata={'timestamp': timezone.now().isoformat()}
        )
        
        SystemMetric.objects.create(
            metric_type='system_memory',
            value=memory.percent,
            metadata={
                'available_gb': round(memory.available / (1024**3), 2),
                'total_gb': round(memory.total / (1024**3), 2)
            }
        )
        
        SystemMetric.objects.create(
            metric_type='system_disk',
            value=(disk.used / disk.total) * 100,
            metadata={
                'free_gb': round(disk.free / (1024**3), 2),
                'total_gb': round(disk.total / (1024**3), 2)
            }
        )
        
        # Vérifier les seuils d'alerte
        if cpu_percent > 80:
            MetricsService._create_alert(
                'system_cpu',
                'high',
                f"CPU usage élevé: {cpu_percent}%",
                80,
                cpu_percent
            )
        
        if memory.percent > 85:
            MetricsService._create_alert(
                'system_memory',
                'high',
                f"Mémoire usage élevé: {memory.percent}%",
                85,
                memory.percent
            )
        
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "disk_percent": (disk.used / disk.total) * 100
        }
        
    except Exception as e:
        logger.error(f"Erreur collecte métriques système: {e}")
        return {"error": str(e)}
    
@shared_task
def generate_daily_report(send_email=False):
    """Génère un rapport quotidien des métriques"""
    try:
        yesterday = timezone.now() - timedelta(days=1)
        
        # Métriques des dernières 24h
        avg_response_time = SystemMetric.objects.filter(
            metric_type='response_time',
            timestamp__gte=yesterday
        ).aggregate(avg=Avg('value'))['avg'] or 0
        
        total_conversations = SystemMetric.objects.filter(
            metric_type='response_time',
            timestamp__gte=yesterday
        ).count()
        
        indexing_success_rate = 0
        indexing_metrics = SystemMetric.objects.filter(
            metric_type='document_indexing',
            timestamp__gte=yesterday
        )
        if indexing_metrics.exists():
            successful = indexing_metrics.filter(value=1.0).count()
            total = indexing_metrics.count()
            indexing_success_rate = (successful / total) * 100
        
        # Alertes créées
        alerts_created = PerformanceAlert.objects.filter(
            created_at__gte=yesterday
        ).count()
        
        # Nouveaux patients
        from patients.models import Patient
        new_patients = Patient.objects.filter(
            created_at__gte=yesterday
        ).count()
        
        report_data = {
            "date": yesterday.date().isoformat(),
            "avg_response_time_ms": round(avg_response_time, 2),
            "total_conversations": total_conversations,
            "indexing_success_rate": round(indexing_success_rate, 2),
            "alerts_created": alerts_created,
            "new_patients": new_patients
        }
        
        # Sauvegarder le rapport
        SystemMetric.objects.create(
            metric_type='daily_report',
            value=1.0,
            metadata=report_data
        )
        
        if send_email:
            # Ici vous pourriez envoyer le rapport par email
            logger.info("Rapport quotidien généré")
        
        return report_data
        
    except Exception as e:
        logger.error(f"Erreur génération rapport quotidien: {e}")
        return {"error": str(e)}
    
@shared_task
def cleanup_old_metrics():
    """Nettoie les anciennes métriques (garde seulement 30 jours)"""
    try:
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_metrics = SystemMetric.objects.filter(
            timestamp__lt=cutoff_date
        ).exclude(metric_type='daily_report')  # Garder les rapports plus longtemps
        
        count = old_metrics.count()
        old_metrics.delete()
        
        logger.info(f"Nettoyage métriques: {count} entrées supprimées")
        return {"deleted_metrics": count}
        
    except Exception as e:
        logger.error(f"Erreur nettoyage métriques: {e}")
        return {"error": str(e)}


def _copy_to_permanent_storage(doc_upload):
    """Copie le fichier uploadé vers le stockage permanent"""
    from django.conf import settings
    
    # Créer le dossier de destination
    patient_folder = os.path.join(
        settings.MEDIA_ROOT, 
        'documents', 
        f'patient_{doc_upload.patient.id}'
    )
    os.makedirs(patient_folder, exist_ok=True)
    
    # Nom du fichier permanent
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{doc_upload.original_filename}"
    dest_path = os.path.join(patient_folder, filename)
    
    # Copier le fichier
    shutil.copy2(doc_upload.file.path, dest_path)
    
    return dest_path

@shared_task
def bulk_index_documents():
    """Tâche pour indexer tous les documents non indexés"""
    documents = Document.objects.filter(pinecone_indexed=False)
    rag_service = RAGService()
    
    indexed_count = 0
    failed_count = 0
    
    for document in documents:
        try:
            success = rag_service.index_document(document)
            if success:
                indexed_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Erreur indexation document {document.id}: {e}")
            failed_count += 1
    
    logger.info(f"Indexation terminée: {indexed_count} succès, {failed_count} échecs")
    return {"indexed": indexed_count, "failed": failed_count}
