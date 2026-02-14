# -*- coding: utf-8 -*-
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from search_engine import build_inverted_index, eval_postfix, infix_to_postfix, load_corpus, query_lex

BASE_DIR = Path(__file__).resolve().parent
CORPUS_PATH = BASE_DIR / "corpusChistes.txt"

STATE: Dict[str, Any] = {"docs": None, "postings": None, "n_docs": 0}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: construir índice una sola vez
    if not CORPUS_PATH.exists():
        raise RuntimeError(f"No se encontró el corpus en: {CORPUS_PATH}")

    docs, n_docs = load_corpus(str(CORPUS_PATH), remap_docids=True)
    postings = build_inverted_index(docs)

    STATE["docs"] = docs
    STATE["postings"] = postings
    STATE["n_docs"] = n_docs

    yield

    # Shutdown: limpiar
    STATE["docs"] = None
    STATE["postings"] = None
    STATE["n_docs"] = 0

app = FastAPI(title="Mini buscador booleano (corpus de chistes)", lifespan=lifespan)

# Frontend estático
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))

@app.get("/search")
def search(
    q: str = Query(..., min_length=1, max_length=200, description="Consulta booleana (AND/OR/NOT, paréntesis)"),
    top: int = Query(10, ge=1, le=100, description="Número de resultados a devolver"),
):
    docs = STATE["docs"]
    postings = STATE["postings"]
    n_docs = STATE["n_docs"]

    if docs is None or postings is None:
        return JSONResponse(status_code=503, content={"error": "Índice aún no listo. Reintenta."})

    try:
        tokens = query_lex(q)
        postfix = infix_to_postfix(tokens)
        hits: List[int] = eval_postfix(postfix, postings, n_docs)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    results = []
    for docid in hits[:top]:
        _id, cat, txt = docs[docid]
        snippet = txt if len(txt) <= 180 else (txt[:177] + "...")
        results.append({"docid": docid, "categoria": cat, "snippet": snippet})

    return {"query": q, "total": len(hits), "top": top, "results": results}
