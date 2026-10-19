"""Pregunta a todas tus fuentes a la vez y obtén una respuesta con citas."""

import argparse
import json
import sys
from pathlib import Path

import anthropic

from llm import ErrorLLM
from pipeline import PipelineRAG, Resultado, describir_modelos


def mostrar(resultado: Resultado, detalle: bool) -> None:
    if detalle:
        print("\n1) Consultas planeadas:")
        for c in resultado.consultas:
            print(f"   - {c}")
        print(f"\n2) Candidatos de la búsqueda híbrida ({len(resultado.candidatos)}):")
        for c in resultado.candidatos:
            p = resultado.puntajes.get(c["id"], "-")
            print(f"   [{p}] {c['id']} ({c['ubicacion']})")
        print(f"\n3) Elegidos tras el re-ranking: {len(resultado.fuentes)}")

    print(f"\n{resultado.respuesta}\n")
    if resultado.fuentes:
        print("Fuentes consultadas:")
        for f in resultado.fuentes:
            print(f"  [{f['numero']}] {f['fuente']} — {f['ubicacion']}")
    if resultado.citas_invalidas:
        print(f"\nAviso: la respuesta cita fuentes que no existen: {resultado.citas_invalidas}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG multi-fuente con búsqueda híbrida, re-ranking y citas.")
    parser.add_argument("pregunta", nargs="?", help="Si no la pasas, entra en modo interactivo")
    parser.add_argument("--indice", type=Path, default=Path("indice.json"))
    parser.add_argument("--detalle", action="store_true", help="Mostrar cada paso del pipeline")
    args = parser.parse_args()

    if not args.indice.exists():
        print(f"No existe {args.indice}. Ejecuta primero: python ingest.py")
        return 1
    pipeline = PipelineRAG(json.loads(args.indice.read_text(encoding="utf-8"))["chunks"])
    print(f"Modelos -> {describir_modelos()}")

    try:
        if args.pregunta:
            mostrar(pipeline.responder(args.pregunta), args.detalle)
            return 0
        print("Modo interactivo. Escribe tu pregunta (o 'salir').")
        while True:
            pregunta = input("> ").strip()
            if pregunta.lower() in {"salir", "exit", "quit"}:
                return 0
            if pregunta:
                try:
                    mostrar(pipeline.responder(pregunta), args.detalle)
                except ErrorLLM as e:
                    print(f"No se pudo responder: {e}\n")
    except ErrorLLM as e:
        print(f"No se pudo responder: {e}")
        return 1
    except anthropic.APIError as e:
        print(f"Error de la API de Claude: {e}")
        return 1
    except (KeyboardInterrupt, EOFError):
        return 0


if __name__ == "__main__":
    sys.exit(main())
