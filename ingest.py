"""Ingesta multi-fuente: carga archivos locales y páginas web, los chunkea según su tipo y guarda el índice."""

import argparse
import json
import sys
import urllib.error
from pathlib import Path

from chunking import CONFIG_POR_TIPO, chunkear
from loaders import cargar_carpeta, cargar_web


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea el índice a partir de archivos (.md, .txt, .pdf) y URLs.")
    parser.add_argument("--fuentes", type=Path, default=Path("fuentes"), help="Carpeta con archivos locales")
    parser.add_argument("--url", action="append", default=[], help="Página web a incluir (se puede repetir)")
    parser.add_argument("--salida", type=Path, default=Path("indice.json"))
    parser.add_argument("--ver", action="store_true", help="Mostrar cada chunk generado")
    args = parser.parse_args()

    documentos = cargar_carpeta(args.fuentes) if args.fuentes.is_dir() else []
    for url in args.url:
        try:
            documentos.append(cargar_web(url))
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print(f"No se pudo descargar {url}: {e}")

    if not documentos:
        print("No hay fuentes para indexar.")
        return 1

    chunks = []
    for doc in documentos:
        propios = chunkear(doc)
        chunks.extend(propios)
        cfg = CONFIG_POR_TIPO[doc.tipo]
        print(
            f"[{doc.tipo:8}] {doc.fuente}: {len(doc.secciones)} secciones -> {len(propios)} chunks "
            f"(tam {cfg['tam']}, solape {cfg['solape']})"
        )

    if args.ver:
        for c in chunks:
            print(f"\n--- {c['id']} | {c['ubicacion']} ({len(c['texto'])} car.) ---\n{c['texto']}")

    args.salida.write_text(json.dumps({"chunks": chunks}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nÍndice guardado en {args.salida}: {len(chunks)} chunks de {len(documentos)} fuentes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
