from celery import shared_task
from .vector_store import load_index, save_index
from rag.models import Document
from sentence_transformers import SentenceTransformer
import faiss, numpy as np, h5py, os, pathlib
from django.utils import timezone

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

@shared_task
def index_document_task(document_id):
    doc = Document.objects.get(id=document_id)
    text = extract_text_from_file(doc.file.path)
    chunks = chunk_text(text)
    embeddings = model.encode(chunks, show_progress_bar=False)
    index = load_index()
    index.add(np.array(embeddings).astype('float32'))
    save_index(index)
    doc.indexed_at = timezone.now()
    doc.save(update_fields=['indexed_at'])

def extract_text_from_file(path):
    # TODO: implement using PyMuPDF, pytesseract, camelot etc.
    return pathlib.Path(path).read_text(errors='ignore')

def chunk_text(text, max_len=512, overlap=50):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i+max_len]
        chunks.append(' '.join(chunk))
        i += max_len - overlap
    return chunks
