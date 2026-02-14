# -*- coding: utf-8 -*-
"""Motor booleano (índice invertido + parser AND/OR/NOT) reutilizable desde FastAPI."""

from __future__ import annotations

import html
import re
import unicodedata
from collections import defaultdict
from typing import Dict, List, Tuple

DOC_RE = re.compile(r'^\s*(\d+)\s*:\s*([^|]+?)\s*\|\s*(.*)$')
TAG_RE = re.compile(r"<[^>]+>")
WORD_RE = re.compile(r"[a-záéíóúüñ0-9]+", re.IGNORECASE)

OPS = {"AND", "OR", "NOT"}
PREC = {"NOT": 3, "AND": 2, "OR": 1}
RIGHT_ASSOC = {"NOT"}  # NOT es unario


def clean_text(s: str) -> str:
    """Des-escapa HTML, elimina tags, normaliza unicode, limpia controles y minúsculas."""
    s = html.unescape(s)
    s = TAG_RE.sub(" ", s)
    s = unicodedata.normalize("NFKC", s)
    s = "".join(
        ch if (unicodedata.category(ch)[0] != "C" or ch in "\n\t ") else " "
        for ch in s
    )
    return s.lower()


def tokenize(s: str) -> List[str]:
    """Extrae tokens (letras/números). Los signos puntúan como separadores."""
    return WORD_RE.findall(s.lower())


def intersect(a: List[int], b: List[int]) -> List[int]:
    """AND: intersección en O(len(a)+len(b)) con dos punteros."""
    i = j = 0
    out: List[int] = []
    la, lb = len(a), len(b)
    while i < la and j < lb:
        da, db = a[i], b[j]
        if da == db:
            out.append(da); i += 1; j += 1
        elif da < db:
            i += 1
        else:
            j += 1
    return out


def union(a: List[int], b: List[int]) -> List[int]:
    """OR: unión en O(len(a)+len(b)) con dos punteros."""
    i = j = 0
    out: List[int] = []
    la, lb = len(a), len(b)
    while i < la and j < lb:
        da, db = a[i], b[j]
        if da == db:
            out.append(da); i += 1; j += 1
        elif da < db:
            out.append(da); i += 1
        else:
            out.append(db); j += 1
    if i < la:
        out.extend(a[i:])
    if j < lb:
        out.extend(b[j:])
    return out


def difference(a: List[int], b: List[int]) -> List[int]:
    r"""A \ B (equiv. A AND NOT B) en O(len(a)+len(b))."""
    i = j = 0
    out: List[int] = []
    la, lb = len(a), len(b)
    while i < la:
        if j >= lb:
            out.extend(a[i:])
            break
        da, db = a[i], b[j]
        if da == db:
            i += 1; j += 1
        elif da < db:
            out.append(da); i += 1
        else:
            j += 1
    return out


def complement(p: List[int], n_docs: int) -> List[int]:
    r"""NOT p = U \ p con U=[0..n_docs-1]. O(n_docs + len(p))."""
    out: List[int] = []
    j = 0
    lp = len(p)
    for d in range(n_docs):
        if j < lp and p[j] == d:
            j += 1
        else:
            out.append(d)
    return out


def query_lex(q: str) -> List[str]:
    """Tokeniza consulta preservando paréntesis y operadores; normaliza términos."""
    q = q.replace("(", " ( ").replace(")", " ) ")
    raw = q.split()
    out: List[str] = []
    for tok in raw:
        up = tok.upper()
        if up in OPS or tok in ("(", ")"):
            out.append(up)
        else:
            out.extend(tokenize(clean_text(tok)))
    return out


def infix_to_postfix(tokens: List[str]) -> List[str]:
    """Shunting-yard para NOT/AND/OR con precedencia NOT > AND > OR."""
    out: List[str] = []
    stack: List[str] = []
    for tok in tokens:
        if tok == "(":
            stack.append(tok)
        elif tok == ")":
            while stack and stack[-1] != "(":
                out.append(stack.pop())
            if not stack:
                raise ValueError("Paréntesis desbalanceados")
            stack.pop()
        elif tok in OPS:
            while stack and stack[-1] in OPS:
                top = stack[-1]
                if ((top in RIGHT_ASSOC and PREC[top] > PREC[tok]) or
                    (top not in RIGHT_ASSOC and PREC[top] >= PREC[tok])):
                    out.append(stack.pop())
                else:
                    break
            stack.append(tok)
        else:
            out.append(tok)
    while stack:
        if stack[-1] in ("(", ")"):
            raise ValueError("Paréntesis desbalanceados")
        out.append(stack.pop())
    return out


def load_corpus(path: str, remap_docids: bool = True) -> Tuple[List[Tuple[int, str, str]], int]:
    """Lee corpus y devuelve docs=(docid, categoria, texto) y n_docs.

    remap_docids=True reasigna docIDs a 0..N-1 para que:
    - el universo del NOT sea [0..N-1]
    - se pueda indexar docs[docid] sin depender del docID original
    """
    raw_docs: List[Tuple[int, str, str]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = DOC_RE.match(line.rstrip("\n"))
            if not m:
                continue
            docid = int(m.group(1))
            cat = m.group(2).strip()
            txt = m.group(3).strip()
            raw_docs.append((docid, cat, txt))

    raw_docs.sort(key=lambda x: x[0])

    if not remap_docids:
        return raw_docs, len(raw_docs)

    docs: List[Tuple[int, str, str]] = []
    for new_id, (_old_id, cat, txt) in enumerate(raw_docs):
        docs.append((new_id, cat, txt))
    return docs, len(docs)


def build_inverted_index(docs: List[Tuple[int, str, str]]) -> Dict[str, List[int]]:
    """Construye índice invertido: término -> postings list (docIDs ordenados)."""
    postings: Dict[str, List[int]] = defaultdict(list)
    for docid, _cat, txt in docs:
        toks = tokenize(clean_text(txt))
        for term in set(toks):  # booleano: presencia/ausencia
            postings[term].append(docid)
    for term in postings:
        postings[term].sort()
    return dict(postings)


def eval_postfix(postfix: List[str], postings: Dict[str, List[int]], n_docs: int) -> List[int]:
    """Evalúa postfix con una pila de postings lists."""
    stack: List[List[int]] = []
    for tok in postfix:
        if tok == "NOT":
            if not stack:
                raise ValueError("NOT sin operando")
            a = stack.pop()
            stack.append(complement(a, n_docs))
        elif tok == "AND":
            if len(stack) < 2:
                raise ValueError("AND sin operandos suficientes")
            b = stack.pop(); a = stack.pop()
            stack.append(intersect(a, b))
        elif tok == "OR":
            if len(stack) < 2:
                raise ValueError("OR sin operandos suficientes")
            b = stack.pop(); a = stack.pop()
            stack.append(union(a, b))
        else:
            stack.append(postings.get(tok, []))
    if len(stack) != 1:
        raise ValueError("Consulta inválida")
    return stack[0]
