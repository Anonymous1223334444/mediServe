class MediRecordBaseException(Exception):
    """Exception de base pour MediRecord"""
    def __init__(self, message, error_code=None, details=None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class RAGException(MediRecordBaseException):
    """Exceptions liées au système RAG"""
    pass

class DocumentProcessingException(MediRecordBaseException):
    """Exceptions liées au traitement des documents"""
    pass

class WhatsAppException(MediRecordBaseException):
    """Exceptions liées à WhatsApp"""
    pass

class N8NException(MediRecordBaseException):
    """Exceptions liées à N8N"""
    pass

class PatientException(MediRecordBaseException):
    """Exceptions liées aux patients"""
    pass

class BroadcastException(MediRecordBaseException):
    """Exceptions liées aux messages diffusés"""
    pass
