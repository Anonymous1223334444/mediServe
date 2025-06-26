# messaging/utils.py
"""
Utilitaires pour la gestion des numéros de téléphone
"""
import re
import logging

logger = logging.getLogger(__name__)

def normalize_phone_number(phone):
    """
    Normalise un numéro de téléphone en format E.164
    Gère les différents formats possibles
    """
    if not phone:
        return None
    
    # Enlever tous les caractères non numériques sauf le +
    cleaned = re.sub(r'[^\d+]', '', str(phone))
    
    # S'assurer que ça commence par +
    if not cleaned.startswith('+'):
        # Si ça commence par 00, remplacer par +
        if cleaned.startswith('00'):
            cleaned = '+' + cleaned[2:]
        else:
            cleaned = '+' + cleaned
    
    logger.debug(f"Normalisation: {phone} → {cleaned}")
    return cleaned


def phones_match(phone1, phone2):
    """
    Compare deux numéros de téléphone de manière flexible
    """
    if not phone1 or not phone2:
        return False
    
    # Normaliser les deux numéros
    norm1 = normalize_phone_number(phone1)
    norm2 = normalize_phone_number(phone2)
    
    # Comparaison exacte
    if norm1 == norm2:
        return True
    
    # Comparaison sans le code pays (pour gérer les cas où l'un a le code et pas l'autre)
    # Prendre les 9 derniers chiffres
    if len(norm1) >= 9 and len(norm2) >= 9:
        if norm1[-9:] == norm2[-9:]:
            logger.debug(f"Match partiel trouvé: {phone1} ≈ {phone2}")
            return True
    
    return False