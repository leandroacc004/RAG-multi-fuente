"""Genera fuentes/informe_anual_2025.pdf sin dependencias (PDF escrito a mano).

Sirve para tener un PDF de ejemplo de varias páginas. Ejecútalo si borras el PDF:
    python scripts/crear_pdf_ejemplo.py
"""

from pathlib import Path

PAGINAS = [
    [
        "Informe anual 2025 - Nimbus Software",
        "",
        "Resumen ejecutivo",
        "En 2025 Nimbus Software alcanzo 4.800 clientes de pago, un 38 % mas que en 2024.",
        "Los ingresos anuales fueron de 6,2 millones de dolares y el margen operativo",
        "llego al 14 %. El plan Empresa ya representa el 52 % de los ingresos.",
        "",
        "Hitos de 2025",
        "- Lanzamiento del modo sin conexion en las aplicaciones de escritorio (marzo).",
        "- Apertura del centro de datos en la Union Europea (junio).",
        "- Certificacion ISO 27001 obtenida en septiembre.",
    ],
    [
        "Clientes y retencion",
        "",
        "La tasa de cancelacion mensual bajo del 3,1 % al 2,2 %. La principal razon de",
        "cancelacion declarada fue el precio en el plan Equipo (41 % de los casos),",
        "seguida por la falta de permisos avanzados (23 %).",
        "",
        "El indice de satisfaccion (NPS) subio de 31 a 44 puntos. Los clientes del plan",
        "Empresa son los mas satisfechos, con un NPS de 58.",
        "",
        "Equipo",
        "La plantilla crecio de 64 a 91 personas. El 60 % trabaja en Ingenieria y Producto.",
    ],
    [
        "Prioridades para 2026",
        "",
        "1. Busqueda: reescribir el motor de busqueda para que sea 10 veces mas rapido y",
        "   ordene los resultados por relevancia. Es la queja numero uno de los clientes.",
        "2. Permisos por grupos y por carpeta, pedido por el 70 % de los clientes Empresa.",
        "3. Auditoria de accesos para cumplir con requisitos de clientes regulados.",
        "4. Reducir el consumo de memoria de la aplicacion de escritorio a la mitad.",
        "",
        "Inversion prevista: 1,5 millones de dolares, con foco en el equipo de Ingenieria.",
        "Objetivo de ingresos 2026: 8,5 millones de dolares.",
    ],
]


def escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def stream_de_pagina(lineas: list[str]) -> bytes:
    partes = ["BT", "/F1 12 Tf", "14 TL", "72 740 Td"]
    for linea in lineas:
        partes.append(f"({escapar(linea)}) Tj T*")
    partes.append("ET")
    return "\n".join(partes).encode("latin-1")


def crear_pdf(destino: Path) -> None:
    n = len(PAGINAS)
    # Objetos: 1 catálogo, 2 páginas, 3 fuente, luego (página, contenido) por cada página
    objetos: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{4 + 2 * i} 0 R' for i in range(n))}] /Count {n} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for i, lineas in enumerate(PAGINAS):
        contenido = stream_de_pagina(lineas)
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode()
        )
        objetos.append(f"<< /Length {len(contenido)} >>\nstream\n".encode() + contenido + b"\nendstream")

    salida = bytearray(b"%PDF-1.4\n")
    offsets = []
    for num, obj in enumerate(objetos, start=1):
        offsets.append(len(salida))
        salida += f"{num} 0 obj\n".encode() + obj + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        salida += f"{off:010d} 00000 n \n".encode()
    salida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(bytes(salida))


if __name__ == "__main__":
    ruta = Path(__file__).resolve().parent.parent / "fuentes" / "informe_anual_2025.pdf"
    crear_pdf(ruta)
    print(f"PDF creado en {ruta}")
