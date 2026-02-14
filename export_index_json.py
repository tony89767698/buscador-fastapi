#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import gzip
import html
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

DOC_RE = re.compile(r'^\s*(\d+)\s*:\s*([^|]+?)\s*\|\s*(.*)$')
TAG_RE = re.compile(r"<[^>]+>")
WORD_RE = re.compile(r"[a-záéíóúüñ0-9]+", re.IGNORECASE)

def clean_text(s: str) -> str:
    """Limpieza ligera: des-escapa HTML, elimina tags, normaliza unicode y minúsculas."""
    s = html.unescape(s)
    s = TAG_RE.sub(" ", s)
    s = unicodedata.normalize("NFKC", s)
    # elimina caracteres de control (excepto espacios/tab/nueva línea)
    s = "".join(ch if (unicodedata.category(ch)[0] != "C" or ch in "\n\t ") else " " for ch in s)
    return s.lower()

def tokenize(s: str):
    """Tokenización simple (solo letras/números); signos separan tokens."""
    return WORD_RE.findall(s.lower())

def load_docs(corpus_path: Path):
    docs = []
    with corpus_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = DOC_RE.match(line.rstrip("\n"))
            if not m:
                continue
            docid = int(m.group(1))
            cat = m.group(2).strip()
            txt = m.group(3).strip()
            docs.append((docid, cat, txt))
    docs.sort(key=lambda x: x[0])
    return docs

def build_inverted_index(docs):
    postings = defaultdict(list)
    for docid, _cat, txt in docs:
        toks = tokenize(clean_text(txt))
        for term in set(toks):           # booleano: presencia/ausencia
            postings[term].append(docid)
    for term in postings:
        postings[term].sort()            # necesario para merges lineales
    return dict(postings)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", help="Ruta al corpusChistes.txt")
    ap.add_argument("--out", default="indice_invertido.json", help="Nombre del archivo .json de salida")
    ap.add_argument("--pretty", action="store_true", help="JSON legible (más grande en tamaño)")
    ap.add_argument("--gzip", action="store_true", help="Además guarda una versión comprimida .json.gz")
    args = ap.parse_args()

    corpus_path = Path(args.corpus)
    if not corpus_path.exists():
        raise FileNotFoundError(f"No existe: {corpus_path}")

    docs = load_docs(corpus_path)
    postings = build_inverted_index(docs)

    out_path = Path(args.out)

    # JSON compacto por defecto (menos bytes)
    if args.pretty:
        json_kwargs = dict(ensure_ascii=False, indent=2)
    else:
        json_kwargs = dict(ensure_ascii=False, separators=(",", ":"))

    with out_path.open("w", encoding="utf-8") as w:
        json.dump(postings, w, **json_kwargs)

    print(f"Docs: {len(docs)}")
    print(f"Vocabulario (términos únicos): {len(postings)}")
    print(f"Guardado: {out_path.resolve()}")

    if args.gzip:
        gz_path = out_path.with_suffix(out_path.suffix + ".gz")
        with gzip.open(gz_path, "wt", encoding="utf-8") as gz:
            json.dump(postings, gz, **json_kwargs)
        print(f"Guardado (gzip): {gz_path.resolve()}")

if __name__ == "__main__":
    main()
