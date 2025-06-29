# messaging/whatsapp_rag_webhook.py
# Webhook WhatsApp avec intégration RAG complète et logging amélioré

import os
import sys
import logging
import time
import re
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from twilio.twiml.messaging_response import MessagingResponse
from django.conf import settings
from django.utils import timezone
import json

# Ajouter le chemin pour les scripts
sys.path.append(os.path.join(settings.BASE_DIR, 'scripts'))

from patients.models import Patient
from documents.models import DocumentUpload
from sessions.models import WhatsAppSession, ConversationLog
from messaging.utils import normalize_phone_number, phones_match

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def whatsapp_rag_webhook(request):
    """Webhook WhatsApp avec RAG intégré"""
    start_time = time.time()
    
    # Logger toutes les données reçues pour debug
    logger.info("="*50)
    logger.info("📱 WEBHOOK TWILIO APPELÉ")
    logger.info(f"Method: {request.method}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"POST data: {dict(request.POST)}")
    logger.info(f"Body: {request.body.decode('utf-8', errors='ignore')[:500]}")  # Premiers 500 chars
    logger.info("="*50)
    
    try:
        # 1. Extraire les données du message - Twilio envoie en POST form-encoded
        from_number = request.POST.get('From', '').replace('whatsapp:', '').replace(' ', '')
        message_body = request.POST.get('Body', '').strip()
        message_sid = request.POST.get('MessageSid', '')
        
        logger.info(f"📱 From: {from_number}")
        logger.info(f"📱 Body: {message_body}")
        logger.info(f"📱 MessageSid: {message_sid}")
        
        # 2. Préparer la réponse Twilio
        resp = MessagingResponse()
        
        # 3. Traiter le message d'activation
        if message_body.upper().startswith('ACTIVER '):
            logger.info("🔑 Message d'activation détecté")
            response_text = handle_activation(from_number, message_body)
            resp.message(response_text)
            logger.info(f"✅ Réponse d'activation envoyée")
            return HttpResponse(str(resp), content_type='text/xml')
        
        # 4. Vérifier que le patient existe et est actif
        try:
            # Normaliser le numéro d'abord
            normalized_from = normalize_phone_number(from_number)
            logger.info(f"🔍 Recherche du patient avec numéro normalisé: {normalized_from}")
            
            # Recherche flexible du patient
            patient = None
            
            # 1. Recherche exacte
            try:
                patient = Patient.objects.get(phone=normalized_from)
                logger.info(f"✅ Patient trouvé par recherche exacte")
            except Patient.DoesNotExist:
                # 2. Recherche avec comparaison flexible
                all_patients = Patient.objects.all()
                for p in all_patients:
                    if phones_match(p.phone, from_number):
                        patient = p
                        logger.info(f"✅ Patient trouvé par comparaison flexible: {p.phone} ≈ {from_number}")
                        break
            
            if not patient:
                raise Patient.DoesNotExist()
            
            logger.info(f"👤 Patient trouvé: {patient.full_name()} (ID: {patient.id})")
            
            if not patient.is_active:
                logger.warning(f"⚠️ Patient non actif: {patient.id}")
                resp.message(f"❌ Veuillez d'abord activer votre compte.\n\nEnvoyez : ACTIVER {patient.activation_token}")
                return HttpResponse(str(resp), content_type='text/xml')
            
        except Patient.DoesNotExist:
            logger.error(f"❌ Patient non trouvé pour le numéro: {from_number} (normalisé: {normalized_from})")
            
            # Logger tous les numéros de patients pour debug
            logger.debug("📱 Numéros de patients dans la DB:")
            for p in Patient.objects.all()[:10]:  # Limiter à 10 pour les logs
                logger.debug(f"  - {p.phone} ({p.full_name()})")
            
            resp.message("❌ Numéro non reconnu. Veuillez contacter votre médecin pour vous inscrire.")
            return HttpResponse(str(resp), content_type='text/xml')
        
        # 5. Créer ou récupérer la session WhatsApp
        session, created = WhatsAppSession.objects.get_or_create(
            patient=patient,
            phone_number=from_number,
            defaults={
                'session_id': f'wa_{patient.id}_{message_sid[:8]}',
                'status': 'active'
            }
        )
        
        # Mettre à jour la dernière activité
        session.last_activity = timezone.now()
        session.save()
        
        logger.info(f"💬 Session {'créée' if created else 'récupérée'}: {session.session_id}")
        
        # 6. Utiliser le RAG pour générer la réponse
        try:
            response_text = process_with_rag(patient, message_body, session)
            
            # 7. Enregistrer la conversation
            response_time_ms = (time.time() - start_time) * 1000
            ConversationLog.objects.create(
                session=session,
                user_message=message_body,
                ai_response=response_text,
                response_time_ms=int(response_time_ms),
                message_length=len(message_body),
                response_length=len(response_text)
            )
            
            logger.info(f"✅ Réponse générée en {response_time_ms:.0f}ms")
            
        except Exception as e:
            logger.error(f"❌ Erreur RAG pour patient {patient.id}: {e}", exc_info=True)
            response_text = (
                "😔 Désolé, je n'ai pas pu traiter votre demande pour le moment.\n\n"
                "Vous pouvez:\n"
                "• Reformuler votre question\n"
                "• Contacter votre médecin directement\n"
                "• Réessayer dans quelques instants"
            )
        
        # 8. Envoyer la réponse
        resp.message(response_text)
        logger.info("✅ Réponse envoyée à Twilio")
        logger.info(f"XML envoyé: {str(resp)}")
        return HttpResponse(str(resp), content_type='text/xml')
        
    except Exception as e:
        logger.error(f"❌ Erreur webhook: {e}", exc_info=True)
        resp = MessagingResponse()
        resp.message("⚠️ Une erreur technique s'est produite. Veuillez réessayer.")
        return HttpResponse(str(resp), content_type='text/xml')


def handle_activation(from_number, message_body):
    """Gère l'activation du patient"""
    try:
        logger.info(f"🔑 Traitement activation pour {from_number}")
        
        # Extraire le token - plus flexible
        # Le token peut être après "ACTIVER " ou juste le UUID
        parts = message_body.split()
        token = None
        
        # Chercher un UUID dans le message
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        matches = re.findall(uuid_pattern, message_body, re.IGNORECASE)
        
        if matches:
            token = matches[0]
            logger.info(f"🔑 Token extrait: {token}")
        else:
            logger.error("❌ Aucun token UUID trouvé dans le message")
            return "❌ Format invalide. Copiez le message complet depuis votre SMS."
        
        # Rechercher le patient par token
        patient = Patient.objects.get(activation_token=token)
        logger.info(f"👤 Patient trouvé par token: {patient.full_name()}")
        
        # Vérifier que le numéro correspond
        if not phones_match(patient.phone, from_number):
            logger.error(f"❌ Numéro non correspondant. Patient: {patient.phone}, From: {from_number}")
            return "❌ Ce lien d'activation ne correspond pas à votre numéro."
        
        if patient.is_active:
            logger.info("✅ Patient déjà actif")
            return f"✅ {patient.first_name}, votre compte est déjà activé ! Comment puis-je vous aider ?"
        
        # Activer le patient
        patient.is_active = True
        patient.activated_at = timezone.now()
        patient.save()
        logger.info(f"✅ Patient activé: {patient.id}")
        
        # Vérifier les documents
        doc_count = DocumentUpload.objects.filter(
            patient=patient, 
            upload_status='indexed'
        ).count()
        
        return f"""✅ Bienvenue {patient.first_name} !

Votre espace santé {settings.HEALTH_STRUCTURE_NAME} est maintenant actif.

{'📄 ' + str(doc_count) + ' document(s) médical(aux) disponible(s)' if doc_count > 0 else '📭 Aucun document pour le moment'}

Je suis votre assistant médical personnel. Je peux vous aider avec :
• 📋 Vos documents médicaux
• 💊 Vos traitements et posologies
• 🔬 Vos résultats d'examens
• ❓ Toute question sur votre santé

Comment puis-je vous aider aujourd'hui ?"""
        
    except Patient.DoesNotExist:
        logger.error(f"❌ Patient non trouvé pour token: {token}")
        return "❌ Token d'activation invalide. Veuillez vérifier votre SMS."
    except Exception as e:
        logger.error(f"❌ Erreur activation: {e}", exc_info=True)
        return "❌ Erreur lors de l'activation. Veuillez contacter le support."


def process_with_rag(patient, query, session):
    """Traite la question avec le système RAG"""
    try:
        logger.info(f"🤖 Traitement RAG pour patient {patient.id} - {patient.full_name()}")
        logger.info(f"📝 Question: {query}")
        
        # Vérifier d'abord les documents indexés
        indexed_docs = DocumentUpload.objects.filter(
            patient=patient,
            upload_status='indexed'
        )
        logger.info(f"📚 Documents indexés pour ce patient: {indexed_docs.count()}")
        for doc in indexed_docs:
            logger.info(f"  - {doc.original_filename} (ID: {doc.id})")
        
        # Importer les modules RAG
        from rag.your_rag_module import (
            VectorStoreHDF5, EmbeddingGenerator, 
            HybridRetriever, GeminiLLM, RAG
        )
        
        # Chemins des fichiers pour ce patient
        vector_dir = os.path.join(settings.MEDIA_ROOT, 'vectors', f'patient_{patient.id}')
        hdf5_path = os.path.join(vector_dir, 'vector_store.h5')
        faiss_path = os.path.join(vector_dir, 'vector_store.faiss')
        bm25_dir = os.path.join(settings.MEDIA_ROOT, 'indexes', f'patient_{patient.id}_bm25')
        
        logger.info(f"📁 Recherche vector store: {hdf5_path}")
        logger.info(f"📁 Existe? {os.path.exists(hdf5_path)}")
        
        # Vérifier l'existence des fichiers
        if not os.path.exists(hdf5_path):
            logger.warning(f"⚠️ Pas de vector store pour patient {patient.id}")
            if indexed_docs.count() > 0:
                logger.error("❌ Documents marqués comme indexés mais pas de vector store!")
                return "⚠️ Vos documents sont en cours de traitement. Veuillez réessayer dans quelques instants."
            return fallback_response(patient, query)
        
        # 1. Charger le vector store
        logger.info(f"📚 Chargement du vector store")
        vector_store = VectorStoreHDF5(hdf5_path)
        vector_store.load_store()
        
        # 2. Initialiser l'embedder
        embedder = EmbeddingGenerator(settings.RAG_SETTINGS.get('EMBEDDING_MODEL', 'all-mpnet-base-v2'))
        
        # 3. Créer le retriever
        if os.path.exists(bm25_dir) and settings.RAG_SETTINGS.get('USE_BM25', True):
            logger.info("🔍 Utilisation du retriever hybride (dense + BM25)")
            retriever = HybridRetriever(vector_store, embedder, bm25_dir)
            
            # Activer le reranking si configuré
            if settings.RAG_SETTINGS.get('USE_RERANKING', True):
                reranker_model = settings.RAG_SETTINGS.get('RERANKER_MODEL', 'cross-encoder/ms-marco-MiniLM-L-6-v2')
                retriever.enable_reranking(reranker_model)
        else:
            logger.info("🔍 Utilisation du retriever dense uniquement")
            retriever = HybridRetriever(vector_store, embedder)
        
        # 4. Initialiser le LLM
        llm = GeminiLLM(model_name=settings.RAG_SETTINGS.get('LLM_MODEL', 'gemini-1.5-flash-latest'))
        
        # 5. Créer le pipeline RAG
        rag = RAG(retriever, llm)
        
        # 6. Personnaliser le prompt pour WhatsApp
        enhanced_query = f"""
        Patient: {patient.first_name} {patient.last_name}
        Question: {query}
        
        Instructions pour l'assistant médical:
        - Répondre en français de manière claire, empathique et professionnelle
        - Utiliser des emojis appropriés pour WhatsApp (🏥 💊 🔬 📋 ✅ etc.)
        - Limiter la réponse à 300 mots maximum
        - Utiliser un langage simple et accessible
        - Si l'information n'est pas dans les documents, le dire clairement
        - Toujours rappeler que pour des décisions médicales importantes, il faut consulter le médecin
        - Éviter le jargon médical complexe
        - Être rassurant tout en restant factuel
        """
        
        # 7. Obtenir la réponse
        logger.info(f"💭 Génération de la réponse RAG")
        response = rag.answer(enhanced_query, top_k=5)
        
        # 8. Post-traiter la réponse
        response = post_process_response(response, patient)
        
        logger.info("✅ Réponse RAG générée avec succès")
        return response
        
    except Exception as e:
        logger.error(f"❌ Erreur RAG: {e}", exc_info=True)
        return fallback_response(patient, query)


def fallback_response(patient, query):
    """Réponse de secours quand le RAG échoue"""
    query_lower = query.lower()
    
    # Réponses basées sur des mots-clés
    if any(word in query_lower for word in ['bonjour', 'salut', 'hello', 'bonsoir']):
        return f"👋 Bonjour {patient.first_name} ! Comment allez-vous aujourd'hui ?"
    
    elif any(word in query_lower for word in ['document', 'fichier', 'dossier']):
        docs = DocumentUpload.objects.filter(patient=patient, upload_status='indexed')
        if docs.exists():
            doc_list = '\n'.join([f"• {doc.original_filename}" for doc in docs[:5]])
            return f"📄 Vos documents disponibles :\n{doc_list}\n\nQue souhaitez-vous savoir ?"
        else:
            return "📭 Aucun document trouvé dans votre dossier. Contactez votre médecin pour les ajouter."
    
    elif any(word in query_lower for word in ['aide', 'help', 'comment', 'quoi']):
        return """🤝 Je peux vous aider avec :
        
• 📋 Consulter vos documents médicaux
• 💊 Informations sur vos médicaments
• 🔬 Comprendre vos résultats d'examens
• 📅 Rappels de rendez-vous
• ❓ Répondre à vos questions de santé

Posez-moi votre question !"""
    
    else:
        return f"""🤔 Je n'ai pas trouvé d'information spécifique sur : "{query}"

Essayez de reformuler ou demandez par exemple :
• "Quels sont mes derniers résultats ?"
• "Quelle est ma posologie actuelle ?"
• "Résume mon dernier rapport médical"

Pour une assistance urgente, contactez votre médecin."""


def post_process_response(response, patient):
    """Post-traite la réponse du RAG pour WhatsApp"""
    # Limiter la longueur
    if len(response) > 1000:
        response = response[:997] + "..."
    
    # Ajouter un footer personnalisé
    footer = f"\n\n_💡 Réponse générée pour {patient.first_name} à {timezone.now().strftime('%H:%M')}_"
    
    # S'assurer que la réponse n'est pas vide
    if not response or response.strip() == "":
        response = "Je n'ai pas pu générer une réponse. Veuillez reformuler votre question."
    
    return response + footer