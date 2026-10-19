"""Chunking con estrategia distinta según el tipo de fuente.

- markdown: cada sección (encabezado) se parte por separado -> un chunk nunca cruza dos temas.
- pdf: cada página se parte por separado -> se puede citar "página N".
- web: el HTML suele tener párrafos cortos y mucho ruido -> chunks más chicos.
- texto: sin estructura -> chunking recursivo genérico.
"""

from loaders import Documento

SEPARADORES = ["\n\n", "\n", ". ", " ", ""]

CONFIG_POR_TIPO = {
    "markdown": {"tam": 900, "solape": 100},
    "pdf": {"tam": 1000, "solape": 150},
    "web": {"tam": 700, "solape": 120},
    "texto": {"tam": 800, "solape": 150},
}


def _unir(partes: list[str], sep: str, tam: int, solape: int) -> list[str]:
    chunks: list[str] = []
    actual: list[str] = []
    for parte in partes:
        if actual and len(sep.join(actual + [parte])) > tam:
            chunks.append(sep.join(actual))
            while actual and (len(sep.join(actual)) > solape or len(sep.join(actual + [parte])) > tam):
                actual.pop(0)
        actual.append(parte)
    if actual:
        chunks.append(sep.join(actual))
    return chunks


def dividir(texto: str, tam: int, solape: int, separadores: list[str] = SEPARADORES) -> list[str]:
    """Chunking recursivo: corta primero por párrafos y baja a separadores más finos solo si hace falta."""
    sep = next((s for s in separadores if s and s in texto), "")
    resto = separadores[separadores.index(sep) + 1:] if sep in separadores else []
    partes = texto.split(sep) if sep else list(texto)
    chunks: list[str] = []
    pequenas: list[str] = []
    for parte in partes:
        if len(parte) <= tam:
            pequenas.append(parte)
            continue
        if pequenas:
            chunks.extend(_unir(pequenas, sep, tam, solape))
            pequenas = []
        chunks.extend(dividir(parte, tam, solape, resto))
    if pequenas:
        chunks.extend(_unir(pequenas, sep, tam, solape))
    return [c.strip() for c in chunks if c.strip()]


def chunkear(doc: Documento) -> list[dict]:
    cfg = CONFIG_POR_TIPO[doc.tipo]
    chunks = []
    for seccion in doc.secciones:
        for parte in dividir(seccion.texto, cfg["tam"], cfg["solape"]):
            chunks.append({
                "id": f"{doc.fuente}#{len(chunks)}",
                "fuente": doc.fuente,
                "tipo": doc.tipo,
                "titulo": doc.titulo,
                "ubicacion": seccion.ubicacion,
                "texto": parte,
            })
    return chunks


def texto_indexable(chunk: dict) -> str:
    """Lo que ven los buscadores: el chunk más su contexto (título del documento y sección)."""
    return f"{chunk['titulo']} | {chunk['ubicacion']}\n{chunk['texto']}"
