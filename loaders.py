"""Cargadores por tipo de fuente.

Cada cargador convierte su formato en una lista de Secciones: pedazos de texto
con una "ubicación" legible (encabezado, página...). La ubicación viaja con cada
chunk y es la que después aparece en las citas.
"""

import re
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader


@dataclass
class Seccion:
    texto: str
    ubicacion: str


@dataclass
class Documento:
    fuente: str
    tipo: str
    titulo: str
    secciones: list[Seccion]


def cargar_markdown(ruta: Path) -> Documento:
    """Separa por encabezados (#, ##, ###): un chunk nunca mezcla dos secciones distintas."""
    texto = ruta.read_text(encoding="utf-8")
    titulo, secciones = ruta.stem, []
    encabezado, lineas = "inicio", []
    for linea in texto.splitlines():
        m = re.match(r"^(#{1,3})\s+(.*)", linea)
        if m:
            if "".join(lineas).strip():
                secciones.append(Seccion("\n".join(lineas).strip(), encabezado))
            if m.group(1) == "#" and titulo == ruta.stem:
                titulo = m.group(2).strip()
            encabezado, lineas = m.group(2).strip(), []
        else:
            lineas.append(linea)
    if "".join(lineas).strip():
        secciones.append(Seccion("\n".join(lineas).strip(), encabezado))
    return Documento(ruta.name, "markdown", titulo, secciones)


def cargar_txt(ruta: Path) -> Documento:
    texto = ruta.read_text(encoding="utf-8")
    primera = next((l.strip() for l in texto.splitlines() if l.strip()), ruta.stem)
    return Documento(ruta.name, "texto", primera[:80], [Seccion(texto, "documento completo")])


def cargar_pdf(ruta: Path) -> Documento:
    """Una sección por página, para poder citar 'página N'."""
    lector = PdfReader(ruta)
    secciones = []
    for n, pagina in enumerate(lector.pages, start=1):
        texto = (pagina.extract_text() or "").strip()
        if texto:
            secciones.append(Seccion(texto, f"página {n}"))
    titulo = secciones[0].texto.splitlines()[0][:80] if secciones else ruta.stem
    return Documento(ruta.name, "pdf", titulo, secciones)


class _ExtractorHTML(HTMLParser):
    """Convierte HTML en secciones usando los encabezados <h1>-<h3> como cortes."""

    IGNORAR = {"script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "form"}
    BLOQUES = {"p", "div", "li", "br", "tr", "section", "article", "table", "ul", "ol", "pre", "blockquote"}

    def __init__(self):
        super().__init__()
        self.secciones: list[Seccion] = []
        self.titulo = ""
        self._encabezado = "inicio"
        self._buffer: list[str] = []
        self._ignorando = 0
        self._en_titulo = False
        self._en_h = False
        self._h_texto: list[str] = []

    def _cerrar_seccion(self):
        texto = re.sub(r"\n{3,}", "\n\n", "".join(self._buffer)).strip()
        texto = re.sub(r"[ \t]+", " ", texto)
        if texto:
            self.secciones.append(Seccion(texto, self._encabezado))
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORAR:
            self._ignorando += 1
        elif tag == "title":
            self._en_titulo = True
        elif tag in {"h1", "h2", "h3"} and not self._ignorando:
            self._cerrar_seccion()
            self._en_h, self._h_texto = True, []
        elif tag in self.BLOQUES:
            self._buffer.append("\n")

    def handle_endtag(self, tag):
        if tag in self.IGNORAR and self._ignorando:
            self._ignorando -= 1
        elif tag == "title":
            self._en_titulo = False
        elif tag in {"h1", "h2", "h3"} and self._en_h:
            self._en_h = False
            self._encabezado = " ".join("".join(self._h_texto).split()) or self._encabezado
        elif tag in self.BLOQUES:
            self._buffer.append("\n")

    def handle_data(self, data):
        if self._en_titulo:
            self.titulo += data
        elif self._ignorando:
            return
        elif self._en_h:
            self._h_texto.append(data)
        else:
            self._buffer.append(data)

    def close(self):
        super().close()
        self._cerrar_seccion()


def cargar_web(url: str) -> Documento:
    pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (RAG-multi-fuente)"})
    with urllib.request.urlopen(pedido, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        html = resp.read().decode(charset, errors="replace")
    extractor = _ExtractorHTML()
    extractor.feed(html)
    extractor.close()
    titulo = " ".join(extractor.titulo.split()) or url
    return Documento(url, "web", titulo[:120], extractor.secciones)


CARGADORES_POR_EXTENSION = {".md": cargar_markdown, ".txt": cargar_txt, ".pdf": cargar_pdf}


def cargar_carpeta(carpeta: Path) -> list[Documento]:
    documentos = []
    for ruta in sorted(carpeta.rglob("*")):
        cargador = CARGADORES_POR_EXTENSION.get(ruta.suffix.lower())
        if cargador and ruta.is_file():
            documentos.append(cargador(ruta))
    return documentos
