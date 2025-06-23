#!/usr/bin/env python3
"""
Script refondu pour extraction multimodale, chunking paramétrable (lexical ou sémantique),
index dense (FAISS + HDF5) et index sparse BM25 (Whoosh),
et tests de retrieval intégrés (FAISS & BM25).
"""
import os
import json
import argparse
import logging
from typing import List, Dict


import collections, collections.abc
for _alias in ("MutableMapping", "Mapping", "Sequence"):
    if not hasattr(collections, _alias):
        setattr(collections, _alias, getattr(collections.abc, _alias))

import numpy as np
import h5py
import faiss
import pdfplumber
import camelot
from PIL import Image
import pytesseract
from sentence_transformers import SentenceTransformer

# Pour chunking sémantique
import nltk
from nltk.tokenize import sent_tokenize
# Télécharger les modèles Punkt pour le français
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)

from whoosh import index as whoosh_index
from whoosh.fields import Schema, TEXT, ID
from whoosh.analysis import RegexTokenizer, LowercaseFilter
from whoosh.qparser import QueryParser

# Liste standard de requêtes de test retrieval
DEFAULT_QUERIES = [
    "What was the unemployment rate in Q2 2020?",
    "Show me the table with population data.",
    "Describe any images related to mortality.",
    "What are the trends in population between 2013 and 2020?",
    "What are the infant mortality rates over the years?",
    "Give me the numerical values for the crude mortality rate.",
    "Summarize the evolution of demographic statistics over the past decade."
]


def extract_text_chunks_lexical(pdf_path: str, chunk_size: int, overlap: int) -> List[Dict]:
    passages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            words = text.split()
            start = 0
            while start < len(words):
                chunk = words[start:start+chunk_size]
                passages.append({"source": "text", "page": page_idx, "text": " ".join(chunk)})
                start += chunk_size - overlap
    return passages


def extract_text_chunks_semantic(pdf_path: str, embedder: SentenceTransformer, threshold: float) -> List[Dict]:
    passages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            # Tokenisation en phrases en français
            sentences = sent_tokenize(text, language='french')
            if not sentences:
                continue
            # Encoder et normaliser chaque phrase
            emb = embedder.encode(sentences, convert_to_numpy=True)
            faiss.normalize_L2(emb)
            # Segmenter par similarité
            chunk_sents: List[str] = []
            chunk_embs: List[np.ndarray] = []
            for sent, vec in zip(sentences, emb):
                if not chunk_embs:
                    chunk_sents = [sent]
                    chunk_embs = [vec]
                else:
                    mean_emb = np.mean(chunk_embs, axis=0)
                    faiss.normalize_L2(mean_emb.reshape(1, -1))
                    sim = float(np.dot(vec, mean_emb))
                    if sim >= threshold:
                        chunk_sents.append(sent)
                        chunk_embs.append(vec)
                    else:
                        passages.append({
                            "source": "text", "page": page_idx,
                            "text": " ".join(chunk_sents)
                        })
                        chunk_sents = [sent]
                        chunk_embs = [vec]
            # Ajouter le dernier chunk s'il existe
            if chunk_sents:
                passages.append({"source": "text", "page": page_idx, "text": " ".join(chunk_sents)})
    return passages


def extract_tables(pdf_path: str) -> List[Dict]:
    passages = []
    tables = camelot.read_pdf(pdf_path, pages="all")
    for tbl in tables:
        html = tbl.df.to_html(index=False)
        passages.append({"source": "table", "page": int(tbl.page) - 1, "text": html})
    return passages


def extract_images_ocr(pdf_path: str) -> List[Dict]:
    passages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            for img_idx, img in enumerate(page.images):
                bbox = (img["x0"], img["top"], img["x1"], img["bottom"])
                try:
                    cropped = page.crop(bbox).to_image(resolution=300)
                    img_arr = cropped.original
                    ocr_text = pytesseract.image_to_string(Image.fromarray(img_arr), lang='fra')
                    passages.append({"source": "image", "page": page_idx, "text": ocr_text})
                except Exception as e:
                    logging.warning(f"OCR failed for image {img_idx} on page {page_idx}: {e}")
    return passages


def init_bm25_index(index_dir: str):
    if whoosh_index is None:
        raise ImportError("Whoosh is required for BM25. Install via 'pip install whoosh'.")
    if not os.path.exists(index_dir):
        os.makedirs(index_dir)
        FR_ANALYZER = RegexTokenizer(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+") \
              | LowercaseFilter()

        schema = Schema(id=ID(stored=True),
                content=TEXT(analyzer=FR_ANALYZER, stored=False))
        idx = whoosh_index.create_in(index_dir, schema)
    else:
        idx = whoosh_index.open_dir(index_dir)
    return idx


def main():
    parser = argparse.ArgumentParser(
        description="Generate embeddings, build vector stores and optionally test retrieval."
    )
    parser.add_argument("--input_dir", required=True, help="Dossier contenant les PDF à traiter.")
    parser.add_argument("--output_hdf5", default="vector_store.h5", help="Fichier HDF5 de sortie.")
    parser.add_argument("--output_faiss", default="vector_store.h5.faiss", help="Fichier FAISS de sortie.")
    parser.add_argument("--bm25_index", default="bm25_index", help="Répertoire pour l'index BM25.")
    parser.add_argument("--with_bm25", action="store_true", help="Construire l'index sparse BM25.")
    parser.add_argument("--embedder", type=str, default="all-mpnet-base-v2", help="Modèle SentenceTransformer.")
    parser.add_argument("--chunk_size", type=int, default=1000, help="Nombre de mots par chunk lexical.")
    parser.add_argument("--overlap", type=int, default=200, help="Chevauchement lexical.")
    parser.add_argument("--semantic_chunking", action="store_true",
                        help="Activer le chunking sémantique (ignore chunk_size/overlap).")
    parser.add_argument("--semantic_threshold", type=float, default=0.8,
                        help="Seuil de similarité pour chunking sémantique.")
    parser.add_argument("--test_retrieval", action="store_true", help="Tester la retrieval après indexation.")
    parser.add_argument("--use_default_queries", action="store_true", help="Utiliser les DEFAULT_QUERIES.")
    parser.add_argument("--test_query", type=str, default="", help="Requête unique pour test retrieval.")
    parser.add_argument("--test_top_k", type=int, default=5, help="Nombre de voisins k pour le test.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger(__name__)

    logger.info(f"Loading embedder '{args.embedder}'")
    embedder = SentenceTransformer(args.embedder)
    dim = embedder.get_sentence_embedding_dimension()

    # Préparer HDF5
    hf = h5py.File(args.output_hdf5, "w")
    vectors = hf.create_dataset("vectors", shape=(0, dim), maxshape=(None, dim), dtype="float32")
    dt = h5py.special_dtype(vlen=bytes)
    metas = hf.create_dataset("metadata", shape=(0,), maxshape=(None,), dtype=dt)

    # Initialiser BM25 si nécessaire
    if args.with_bm25:
        bm25_idx = init_bm25_index(args.bm25_index)
        bm25_writer = bm25_idx.writer()

    count = 0
    for fname in os.listdir(args.input_dir):
        if not fname.lower().endswith(".pdf"): continue
        path = os.path.join(args.input_dir, fname)
        passages = (extract_text_chunks_semantic(path, embedder, args.semantic_threshold)
                    if args.semantic_chunking else
                    extract_text_chunks_lexical(path, args.chunk_size, args.overlap))
        passages.extend(extract_tables(path))
        passages.extend(extract_images_ocr(path))
        for p_i, passage in enumerate(passages):
            pid = f"{os.path.splitext(fname)[0]}_{passage['source']}_p{passage['page']}_c{p_i}"
            vec = embedder.encode(passage['text'], convert_to_numpy=True)
            faiss.normalize_L2(vec.reshape(1, -1))
            vectors.resize((count+1, dim))
            vectors[count] = vec
            metas.resize((count+1,))
            metas[count] = json.dumps({
               "id": pid,
               "source": passage['source'],
               "type": passage['source'],
               "page": passage['page'],
               "embedder": args.embedder
            }).encode()
            if args.with_bm25:
                bm25_writer.add_document(id=pid, content=passage['text'])
            count += 1

    hf.close()
    logger.info(f"Saved {count} vectors to '{args.output_hdf5}'")
    if args.with_bm25:
        bm25_writer.commit()

    # Build FAISS
    faiss_idx = faiss.IndexFlatIP(dim)
    with h5py.File(args.output_hdf5, "r") as hf2:
        all_vecs = hf2["vectors"][:]  # type: ignore
    faiss.normalize_L2(all_vecs)
    faiss_idx.add(all_vecs)
    faiss.write_index(faiss_idx, args.output_faiss)

    # Tests retrieval
    def run_tests(queries: List[str]):
        with h5py.File(args.output_hdf5, "r") as hf2:
            metas2 = hf2["metadata"][:]
            for q in queries:
                logger.info(f"--- Query: '{q}' ---")
                qvec = embedder.encode(q, convert_to_numpy=True)
                faiss.normalize_L2(qvec.reshape(1, -1))
                D, I = faiss_idx.search(qvec.reshape(1, -1), args.test_top_k)
                for rank, (i, dist) in enumerate(zip(I[0], D[0]), 1):
                    m = json.loads(metas2[i].decode())
                    logger.info(f"{rank}. {m['id']} ({m['source']}) dist={dist:.4f}")
                if args.with_bm25:
                    searcher = bm25_idx.searcher()
                    qp = QueryParser("content", bm25_idx.schema)
                    res = searcher.search(qp.parse(q), limit=args.test_top_k)
                    for rrank, hit in enumerate(res, 1):
                        logger.info(f"{rrank}. {hit['id']} score={hit.score:.4f}")
                    searcher.close()

    if args.test_retrieval:
        if args.use_default_queries:
            run_tests(DEFAULT_QUERIES)
        elif args.test_query:
            run_tests([args.test_query])
        else:
            logger.error("--test_retrieval requires --test_query or --use_default_queries.")

if __name__ == "__main__":
    main()
