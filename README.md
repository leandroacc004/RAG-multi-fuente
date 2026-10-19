# RAG multi-fuente

Un RAG de nivel avanzado que responde preguntas usando **varias fuentes a la vez** (PDFs, Markdown, texto plano y páginas web), con búsqueda híbrida, re-ranking con IA, respuestas con citas verificables y un evaluador para medir la calidad.

Si ya hiciste el proyecto *RAG for docs*, este es el siguiente paso: cada pieza que allí era simple aquí se vuelve una etapa que se puede medir y mejorar.

## Arquitectura

```
INGESTA
  fuentes/*.pdf ─► una sección por página ─┐
  fuentes/*.md  ─► una sección por título ─┼─► chunking según el tipo ─► indice.json
  fuentes/*.txt ─► documento completo     ─┤   (tamaño y solape propios)
  --url ...     ─► secciones por <h1>-<h3> ─┘

CONSULTA (pipeline.py)
  pregunta
    │
    ├─1─► PLANEAR      Claude (rápido) reescribe la pregunta en 1-3 consultas
    ├─2─► RECUPERAR    BM25 + n-gramas por cada consulta ─► fusión RRF ─► 12 candidatos
    ├─3─► RE-RANKEAR   Claude (rápido) puntúa 0-3 cada candidato ─► quedan los ≥2 (máx. 5)
    └─4─► GENERAR      Claude responde solo con esas fuentes y cita [1], [2]...
                       └─► se verifica que cada cita exista
```

## Conceptos clave

| Concepto | Dónde verlo | Qué resuelve |
|---|---|---|
| **Cargadores por formato** | `loaders.py` | Cada formato tiene su estructura natural (páginas, títulos, encabezados HTML) y se conserva como "ubicación" para las citas. |
| **Chunking por tipo de fuente** | `chunking.py` → `CONFIG_POR_TIPO` | Un PDF denso y una página web ruidosa no se parten igual. Los chunks nunca cruzan dos secciones. |
| **Contexto en el chunk** | `texto_indexable()` | El chunk se indexa con el título del documento y su sección, así "son 100 por minuto" se encuentra al buscar "límites de la API". |
| **Búsqueda híbrida** | `buscador.py` | BM25 acierta con palabras exactas; los n-gramas de caracteres toleran variaciones ("cancelan" ≈ "cancelación"). |
| **Reciprocal Rank Fusion** | `rrf()` | Combina rankings por **posición**, no por puntaje, porque cada buscador puntúa en una escala distinta. |
| **Query planning** | `planear_consultas()` | Una pregunta como "¿cuánto se facturó y qué viene para 2026?" son dos búsquedas distintas. |
| **Re-ranking** | `reordenar()` | La búsqueda es rápida pero aproximada; un modelo lee los candidatos y decide cuáles sirven de verdad. |
| **Citas verificables** | `generar()` | Las citas se comprueban en código: si el modelo cita `[7]` y solo hay 5 fuentes, se avisa. |
| **Modelos por etapa** | `llm.py` | Las etapas repetitivas usan un modelo barato; solo la respuesta final usa el modelo grande. |
| **Evaluación** | `eval.py` + `evalset.json` | Sin medir no sabes si un cambio mejora o empeora. |

## Estructura

| Archivo | Para qué sirve |
|---|---|
| `loaders.py` | Cargadores de Markdown, texto, PDF (`pypdf`) y web (HTML → secciones, sin dependencias extra) |
| `chunking.py` | Chunking recursivo con configuración por tipo de fuente |
| `buscador.py` | BM25, n-gramas de caracteres, RRF y el buscador híbrido |
| `pipeline.py` | Las 4 etapas: planear, recuperar, re-rankear y generar |
| `ingest.py` | Crea `indice.json` a partir de `fuentes/` y de URLs |
| `ask.py` | CLI para preguntar (con `--detalle` muestra cada etapa) |
| `eval.py` | Evaluación de la búsqueda (gratis) y del pipeline completo |
| `evalset.json` | Preguntas de evaluación con la fuente y los datos esperados |
| `fuentes/` | Fuentes de ejemplo: un PDF de 3 páginas, un manual en Markdown y una política en texto |
| `scripts/crear_pdf_ejemplo.py` | Regenera el PDF de ejemplo sin dependencias |

## Instalación

Necesitas Python 3.10 o superior y una API key de Anthropic ([console.anthropic.com](https://console.anthropic.com)).

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY="tu-api-key"   # Windows: set ANTHROPIC_API_KEY=tu-api-key
```

## Uso

```bash
# 1. Indexar las fuentes locales (y, si quieres, páginas web)
python ingest.py
python ingest.py --url https://ejemplo.com/una-pagina --url https://ejemplo.com/otra

# 2. Preguntar
python ask.py "¿Cuántas peticiones por minuto permite la API en el plan Empresa?"
python ask.py "¿Cuánto facturó la empresa en 2025 y cuáles son las prioridades para 2026?" --detalle

# 3. Evaluar
python eval.py --solo-busqueda          # gratis: compara BM25, n-gramas e híbrido
python eval.py --solo-busqueda --k 1    # más exigente: la fuente correcta debe salir primera
python eval.py                          # pipeline completo (usa la API)
```

Salida de ejemplo con `--detalle`:

```
1) Consultas planeadas:
   - ¿Cuántas peticiones por minuto permite la API en el plan Empresa?
   - límite de peticiones por minuto API
   - rate limit plan Empresa

2) Candidatos de la búsqueda híbrida (10):
   [3] manual_api.md#1 (Límites de uso)
   [1] manual_api.md#4 (Errores comunes)
   [0] informe_anual_2025.pdf#0 (página 1)
   ...

3) Elegidos tras el re-ranking: 1

En el plan Empresa el límite es de 1.000 peticiones por minuto por token [1]. Si se supera,
la API responde con el código 429 y la cabecera Retry-After [1].

Fuentes consultadas:
  [1] manual_api.md — Límites de uso
```

## Configuración

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Tu API key (obligatoria) |
| `CLAUDE_MODEL` | `claude-opus-5-5` | Modelo que redacta la respuesta final |
| `CLAUDE_MODEL_RAPIDO` | `claude-haiku-5-5` | Modelo de la planificación y el re-ranking |

Los parámetros del pipeline (`CANDIDATOS`, `SELECCION_MAX`, `RELEVANCIA_MINIMA`) están al inicio de `pipeline.py`, y los tamaños de chunk en `CONFIG_POR_TIPO` (`chunking.py`).

## Experimentos recomendados

1. **Agrega preguntas difíciles a `evalset.json`** (sinónimos, preguntas que combinan dos fuentes) hasta que `--solo-busqueda` empiece a fallar. Ahí es donde se nota la diferencia entre buscadores.
2. **Cambia `CONFIG_POR_TIPO`** y vuelve a correr `ingest.py` + `eval.py --solo-busqueda`. ¿Chunks más chicos mejoran o empeoran?
3. **Desactiva el re-ranking** (devuelve `candidatos[:5]` en `reordenar`) y compara la calidad de las respuestas con `eval.py`.
4. **Agrega embeddings** como tercer buscador dentro de `BuscadorHibrido` (Anthropic recomienda [Voyage AI](https://docs.claude.com/en/docs/build-with-claude/embeddings)); RRF los combina sin cambiar nada más.
5. **Prompt caching:** si haces muchas preguntas sobre las mismas fuentes, cachea el bloque de fuentes con `cache_control` para ahorrar costos.
