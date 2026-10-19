"""Búsqueda híbrida: dos buscadores distintos combinados con Reciprocal Rank Fusion (RRF).

- BM25 (palabras exactas): muy preciso cuando la pregunta usa las mismas palabras que el documento.
- N-gramas de caracteres: compara pedazos de 3 letras, así "recupero" se parece a "recuperar"
  y "cancelaciones" a "cancelación". Tolera variaciones de palabras y errores de tipeo.
- RRF: en vez de mezclar puntajes (que están en escalas distintas), mezcla POSICIONES:
  cada chunk suma 1 / (k + posición) en cada lista donde aparece.
"""

import math
import re
import unicodedata
from collections import Counter, defaultdict

STOPWORDS = set(
    "a al algo algunas algunos ante antes como con contra cual cuando de del desde donde durante e el ella "
    "ellas ellos en entre era es esa esas ese eso esos esta estas este esto estos fue ha hay la las le les lo "
    "los mas me mi mis muy ni no nos o os otra otro para pero poco por porque que quien se sea ser si sin "
    "sobre son su sus tambien te tiene tu tus un una unas uno unos y ya yo puedo puede cuanto cuantos cuantas".split()
)


def sin_tildes(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def tokenizar(texto: str) -> list[str]:
    tokens = []
    for palabra in re.findall(r"\w+", sin_tildes(texto)):
        if len(palabra) > 4 and palabra.endswith("es"):
            palabra = palabra[:-2]
        elif len(palabra) > 3 and palabra.endswith("s"):
            palabra = palabra[:-1]
        if palabra not in STOPWORDS and len(palabra) > 1:
            tokens.append(palabra)
    return tokens


class BM25:
    def __init__(self, documentos: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenizar(d)) for d in documentos]
        self.largos = [sum(c.values()) for c in self.docs]
        self.largo_medio = sum(self.largos) / max(len(self.docs), 1)
        df = Counter(t for doc in self.docs for t in doc)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def buscar(self, consulta: str, k: int) -> list[int]:
        terminos = tokenizar(consulta)
        puntajes = []
        for i, (doc, largo) in enumerate(zip(self.docs, self.largos)):
            s = 0.0
            for t in terminos:
                tf = doc.get(t, 0)
                if tf:
                    s += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * largo / self.largo_medio))
            if s > 0:
                puntajes.append((s, i))
        return [i for _, i in sorted(puntajes, reverse=True)[:k]]


def ngramas(texto: str, n: int = 3) -> Counter:
    palabras = [p for p in re.findall(r"\w+", sin_tildes(texto)) if p not in STOPWORDS]
    grams = Counter()
    for p in palabras:
        p = f" {p} "
        grams.update(p[i:i + n] for i in range(len(p) - n + 1))
    return grams


class NGramas:
    """Similitud coseno entre vectores TF-IDF de trigramas de caracteres."""

    def __init__(self, documentos: list[str]):
        conteos = [ngramas(d) for d in documentos]
        df = Counter(g for c in conteos for g in c)
        n = len(conteos)
        self.idf = {g: math.log((n + 1) / (f + 1)) + 1 for g, f in df.items()}
        self.vectores = [self._vector(c) for c in conteos]

    def _vector(self, conteo: Counter) -> dict:
        v = {g: tf * self.idf.get(g, 0.0) for g, tf in conteo.items()}
        norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {g: x / norma for g, x in v.items()}

    def buscar(self, consulta: str, k: int, minimo: float = 0.05) -> list[int]:
        q = self._vector(ngramas(consulta))
        puntajes = []
        for i, v in enumerate(self.vectores):
            s = sum(peso * v.get(g, 0.0) for g, peso in q.items())
            if s >= minimo:
                puntajes.append((s, i))
        return [i for _, i in sorted(puntajes, reverse=True)[:k]]


def rrf(listas: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: combina rankings sin importar en qué escala puntúa cada buscador."""
    puntaje = defaultdict(float)
    for lista in listas:
        for posicion, indice in enumerate(lista, start=1):
            puntaje[indice] += 1.0 / (k + posicion)
    return sorted(puntaje.items(), key=lambda x: x[1], reverse=True)


class BuscadorHibrido:
    def __init__(self, textos: list[str]):
        self.bm25 = BM25(textos)
        self.ngramas = NGramas(textos)

    def buscar(self, consultas: list[str], k_por_lista: int = 10, k_final: int = 12) -> list[int]:
        listas = []
        for consulta in consultas:
            listas.append(self.bm25.buscar(consulta, k_por_lista))
            listas.append(self.ngramas.buscar(consulta, k_por_lista))
        return [i for i, _ in rrf(listas)[:k_final]]
