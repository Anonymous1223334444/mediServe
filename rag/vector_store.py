from pathlib import Path
import faiss, numpy as np, h5py, os, json
from dotenv import load_dotenv


VECTOR_DIM = 768
INDEX_PATH = os.getenv('VECTOR_INDEX_PATH', 'vector_store.faiss')
HDF5_PATH = os.getenv('VECTOR_HDF5_PATH', 'vector_store.h5')

def load_index():
    if not Path(INDEX_PATH).exists():
        index = faiss.IndexFlatL2(VECTOR_DIM)
        faiss.write_index(index, INDEX_PATH)
    return faiss.read_index(INDEX_PATH)

def save_index(index):
    faiss.write_index(index, INDEX_PATH)
