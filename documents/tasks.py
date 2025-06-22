# documents/tasks.py - Version simplifiée et corrigée

from celery import shared_task, current_task
from django.utils import timezone
from .models import DocumentUpload
import logging
import os
import subprocess
from django.conf import settings

logger = logging.getLogger(__name__)

@shared_task(bind=True, name='documents.tasks.process_document_async')
def process_document_async(self, document_upload_id):
    """
    Tâche Celery pour traiter un document uploadé
    """
    logger.info(f"[DÉBUT] Traitement du document {document_upload_id}")
    
    try:
        # 1. Récupérer le document
        doc_upload = DocumentUpload.objects.get(id=document_upload_id)
        
        # Sauvegarder le task_id si le champ existe
        if hasattr(doc_upload, 'celery_task_id'):
            doc_upload.celery_task_id = self.request.id
            doc_upload.save(update_fields=['celery_task_id'])
        
        # 2. Vérifier que le fichier existe
        if not doc_upload.file or not os.path.exists(doc_upload.file.path):
            logger.error(f"Fichier manquant pour document {document_upload_id}")
            doc_upload.upload_status = 'failed'
            doc_upload.error_message = "Fichier physique introuvable"
            doc_upload.save()
            return {"status": "error", "error": "Fichier manquant"}
        
        # 3. Mettre à jour le statut
        doc_upload.upload_status = 'processing'
        doc_upload.save()
        
        # Mettre à jour la progression
        self.update_state(
            state='PROGRESS',
            meta={'current': 10, 'total': 100, 'status': 'Initialisation...'}
        )
        
        # 4. Préparer et exécuter le script de vectorisation
        script_path = os.path.join(settings.BASE_DIR, 'scripts', 'vectorize_document.sh')
        
        if not os.path.exists(script_path):
            logger.error(f"Script non trouvé: {script_path}")
            doc_upload.upload_status = 'failed'
            doc_upload.error_message = "Script de vectorisation non trouvé"
            doc_upload.save()
            return {"status": "error", "error": "Script non trouvé"}
        
        # S'assurer que le script est exécutable
        os.chmod(script_path, 0o755)
        
        self.update_state(
            state='PROGRESS',
            meta={'current': 30, 'total': 100, 'status': 'Vectorisation en cours...'}
        )
        
        # 5. Exécuter le script
        logger.info(f"Exécution: {script_path} {document_upload_id}")
        
        env = os.environ.copy()
        env['DJANGO_SETTINGS_MODULE'] = 'mediServe.settings'
        env['PYTHONPATH'] = settings.BASE_DIR
        
        process = subprocess.Popen(
            [script_path, str(document_upload_id)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            env=env,
            cwd=settings.BASE_DIR
        )
        
        # Lire la sortie ligne par ligne
        output_lines = []
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                logger.info(f"[SCRIPT] {line}")
                output_lines.append(line)
                
                # Mettre à jour la progression basée sur la sortie
                if "Vectorisation réussie" in line:
                    self.update_state(
                        state='PROGRESS',
                        meta={'current': 80, 'total': 100, 'status': 'Finalisation...'}
                    )
        
        process.stdout.close()
        return_code = process.wait()
        
        # 6. Traiter le résultat
        if return_code == 0:
            logger.info(f"✅ Document {document_upload_id} traité avec succès")
            
            self.update_state(
                state='PROGRESS',
                meta={'current': 100, 'total': 100, 'status': 'Terminé!'}
            )
            
            # Envoyer une notification WhatsApp si configuré
            try:
                from messaging.services import WhatsAppService
                whatsapp = WhatsAppService()
                patient = doc_upload.patient
                
                message = f"✅ {patient.first_name}, votre document '{doc_upload.original_filename}' a été traité avec succès."
                whatsapp.send_message(patient.phone, message)
            except Exception as e:
                logger.warning(f"Notification WhatsApp échouée: {e}")
            
            return {
                "status": "success",
                "document_id": document_upload_id,
                "message": "Document indexé avec succès"
            }
        else:
            logger.error(f"❌ Échec du traitement (code {return_code})")
            doc_upload.upload_status = 'failed'
            doc_upload.error_message = f"Échec de la vectorisation (code {return_code})"
            doc_upload.save()
            
            return {
                "status": "error",
                "document_id": document_upload_id,
                "return_code": return_code,
                "output": '\n'.join(output_lines[-10:])  # Dernières 10 lignes
            }
            
    except DocumentUpload.DoesNotExist:
        logger.error(f"Document {document_upload_id} non trouvé")
        return {"status": "error", "error": "Document non trouvé"}
        
    except Exception as e:
        logger.exception(f"Erreur inattendue: {e}")
        try:
            doc_upload = DocumentUpload.objects.get(id=document_upload_id)
            doc_upload.upload_status = 'failed'
            doc_upload.error_message = str(e)
            doc_upload.save()
        except:
            pass
        return {"status": "error", "error": str(e)}

# Tâche pour envoyer le SMS après création du patient
@shared_task(name='documents.tasks.send_patient_activation_sms')
def send_patient_activation_sms(patient_id):
    """Envoie le SMS d'activation au patient"""
    try:
        from patients.models import Patient
        from messaging.services import SMSService
        
        patient = Patient.objects.get(id=patient_id)
        sms_service = SMSService()
        
        success, result = sms_service.send_activation_sms(patient)
        
        if success:
            logger.info(f"✅ SMS envoyé à {patient.phone}")
            return {"status": "success", "sms_id": result}
        else:
            logger.error(f"❌ Échec envoi SMS: {result}")
            return {"status": "error", "error": result}
            
    except Exception as e:
        logger.exception(f"Erreur envoi SMS: {e}")
        return {"status": "error", "error": str(e)}

# Les autres tâches existantes...