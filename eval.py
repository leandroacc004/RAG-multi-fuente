"""Evaluación del RAG: mide si el sistema encuentra la fuente correcta y si la respuesta contiene lo esperado.

Dos modos:
  python eval.py --solo-busqueda   # gratis, sin API: compara BM25 vs n-gramas vs híbrido
  python eval.py                   # pipeline completo con Claude (cuesta tokens)
"""

import argparse
import json
import sys
from pathlib import Path

import anthropic

from buscador import BM25, BuscadorHibrido, NGramas, sin_tildes
from chunking import texto_indexable
from llm import ErrorLLM
from pipeline import PipelineRAG


def acierto(chunks: list[dict], indices: list[int], fuente_esperada: str) -> bool:
    return any(chunks[i]["fuente"] == fuente_esperada for i in indices)


def evaluar_busqueda(chunks: list[dict], casos: list[dict], k: int) -> None:
    textos = [texto_indexable(c) for c in chunks]
    hibrido = BuscadorHibrido(textos)
    buscadores = {
        "BM25": BM25(textos).buscar,
        "N-gramas": NGramas(textos).buscar,
        "Híbrido": lambda q, k: hibrido.buscar([q], k_final=k),
    }
    totales = {nombre: 0 for nombre in buscadores}
    print(f"{'Pregunta':58} " + " ".join(f"{n:>9}" for n in buscadores))
    for caso in casos:
        fila = []
        for nombre, buscar in buscadores.items():
            ok = acierto(chunks, buscar(caso["pregunta"], k), caso["fuente_esperada"])
            totales[nombre] += ok
            fila.append("ok" if ok else "FALLA")
        print(f"{caso['pregunta'][:58]:58} " + " ".join(f"{v:>9}" for v in fila))
    print(f"\nAcierto@{k} (la fuente correcta aparece entre los {k} primeros):")
    for nombre, total in totales.items():
        print(f"  {nombre:9} {total}/{len(casos)} ({100 * total / len(casos):.0f} %)")


def evaluar_pipeline(chunks: list[dict], casos: list[dict]) -> None:
    pipeline = PipelineRAG(chunks)
    fuente_ok = claves_ok = 0
    for caso in casos:
        try:
            r = pipeline.responder(caso["pregunta"])
        except ErrorLLM as e:
            print(f"ERROR   {caso['pregunta']} ({e})")
            continue
        encontro = any(f["fuente"] == caso["fuente_esperada"] for f in r.fuentes)
        respuesta = sin_tildes(r.respuesta)
        faltan = [p for p in caso["palabras_clave"] if sin_tildes(p) not in respuesta]
        fuente_ok += encontro
        claves_ok += not faltan
        estado = "ok" if encontro and not faltan else "FALLA"
        detalle = "" if not faltan else f" (faltan: {', '.join(faltan)})"
        print(f"{estado:6} {caso['pregunta']}{detalle}")
    n = len(casos)
    print(f"\nFuente correcta entre las elegidas: {fuente_ok}/{n} | Respuesta con los datos esperados: {claves_ok}/{n}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalúa la búsqueda o el pipeline completo.")
    parser.add_argument("--indice", type=Path, default=Path("indice.json"))
    parser.add_argument("--casos", type=Path, default=Path("evalset.json"))
    parser.add_argument("--solo-busqueda", action="store_true", help="Evaluar solo la búsqueda (sin API)")
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()

    if not args.indice.exists():
        print(f"No existe {args.indice}. Ejecuta primero: python ingest.py")
        return 1
    chunks = json.loads(args.indice.read_text(encoding="utf-8"))["chunks"]
    casos = json.loads(args.casos.read_text(encoding="utf-8"))

    if args.solo_busqueda:
        evaluar_busqueda(chunks, casos, args.k)
        return 0
    try:
        evaluar_pipeline(chunks, casos)
    except anthropic.APIError as e:
        print(f"Error de la API de Claude: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
