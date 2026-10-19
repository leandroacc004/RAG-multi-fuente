"""Pipeline RAG orquestado en 4 pasos.

  1. Planear:     Claude reescribe la pregunta en 1-3 consultas de búsqueda.
  2. Recuperar:   búsqueda híbrida (BM25 + n-gramas) para cada consulta, fusionada con RRF.
  3. Re-rankear:  Claude puntúa la relevancia real de cada candidato y se quedan los mejores.
  4. Generar:     Claude responde solo con los chunks elegidos, citando [1], [2], ...

Cada paso es una pieza independiente: puedes medirla, cambiarla o saltarla.
"""

import re
from dataclasses import dataclass, field

from buscador import BuscadorHibrido
from chunking import texto_indexable
from llm import MODELO, MODELO_RAPIDO, crear_mensaje, pedir_json, texto

MAX_CONSULTAS = 3
CANDIDATOS = 12
SELECCION_MAX = 5
RELEVANCIA_MINIMA = 2

SYSTEM_RESPUESTA = (
    "Respondes preguntas usando únicamente las fuentes numeradas que se te entregan. "
    "Después de cada afirmación pon la cita con el número de la fuente entre corchetes, por ejemplo [2]. "
    "Si las fuentes no alcanzan para responder, dilo y explica qué falta. No inventes datos. Responde en español."
)


@dataclass
class Resultado:
    respuesta: str
    fuentes: list[dict]
    consultas: list[str] = field(default_factory=list)
    candidatos: list[dict] = field(default_factory=list)
    puntajes: dict = field(default_factory=dict)
    citas_invalidas: list[int] = field(default_factory=list)


class PipelineRAG:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.buscador = BuscadorHibrido([texto_indexable(c) for c in chunks])

    # 1. Planear
    def planear_consultas(self, pregunta: str) -> list[str]:
        schema = {
            "type": "object",
            "properties": {"consultas": {"type": "array", "items": {"type": "string"}}},
            "required": ["consultas"],
            "additionalProperties": False,
        }
        prompt = (
            f"Pregunta del usuario: {pregunta}\n\n"
            f"Escribe entre 1 y {MAX_CONSULTAS} consultas de búsqueda por palabras clave para encontrar la "
            "información necesaria. Si la pregunta combina varios temas, usa una consulta por tema. "
            "Incluye sinónimos útiles."
        )
        consultas = [c.strip() for c in pedir_json(prompt, schema)["consultas"] if c.strip()]
        return [pregunta] + consultas[:MAX_CONSULTAS]

    # 2. Recuperar
    def recuperar(self, consultas: list[str]) -> list[dict]:
        return [self.chunks[i] for i in self.buscador.buscar(consultas, k_final=CANDIDATOS)]

    # 3. Re-rankear
    def reordenar(self, pregunta: str, candidatos: list[dict]) -> tuple[list[dict], dict]:
        schema = {
            "type": "object",
            "properties": {
                "evaluaciones": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}, "relevancia": {"type": "integer"}},
                        "required": ["id", "relevancia"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["evaluaciones"],
            "additionalProperties": False,
        }
        # Ids cortos (c1, c2...) para que el modelo no tenga que copiar ids largos
        por_alias = {f"c{n}": c for n, c in enumerate(candidatos, start=1)}
        bloques = "\n".join(
            f'<candidato id="{alias}" fuente="{c["fuente"]}" ubicacion="{c["ubicacion"]}">\n{c["texto"]}\n</candidato>'
            for alias, c in por_alias.items()
        )
        prompt = (
            f"{bloques}\n\nPregunta: {pregunta}\n\n"
            "Puntúa cada candidato según cuánto ayuda a responder la pregunta: "
            "0 = nada, 1 = tangencial, 2 = útil, 3 = contiene la respuesta. Evalúa todos los candidatos."
        )
        evaluaciones = pedir_json(prompt, schema)["evaluaciones"]
        puntajes = {e["id"]: max(0, min(3, e["relevancia"])) for e in evaluaciones if e["id"] in por_alias}
        orden = sorted(por_alias, key=lambda a: puntajes.get(a, 0), reverse=True)
        elegidos = [por_alias[a] for a in orden if puntajes.get(a, 0) >= RELEVANCIA_MINIMA][:SELECCION_MAX]
        return elegidos, {por_alias[a]["id"]: p for a, p in puntajes.items()}

    # 4. Generar
    def generar(self, pregunta: str, seleccion: list[dict]) -> tuple[str, list[int]]:
        bloques = "\n".join(
            f'<fuente numero="{n}" origen="{c["fuente"]}" ubicacion="{c["ubicacion"]}">\n{c["texto"]}\n</fuente>'
            for n, c in enumerate(seleccion, start=1)
        )
        resp = crear_mensaje(
            modelo=MODELO,
            max_tokens=16000,
            system=SYSTEM_RESPUESTA,
            messages=[{"role": "user", "content": f"<fuentes>\n{bloques}\n</fuentes>\n\nPregunta: {pregunta}"}],
        )
        respuesta = texto(resp)
        citadas = {int(n) for n in re.findall(r"\[(\d+)\]", respuesta)}
        invalidas = sorted(n for n in citadas if not 1 <= n <= len(seleccion))
        return respuesta, invalidas

    def responder(self, pregunta: str) -> Resultado:
        consultas = self.planear_consultas(pregunta)
        candidatos = self.recuperar(consultas)
        if not candidatos:
            return Resultado("No encontré información relacionada en las fuentes.", [], consultas)

        seleccion, puntajes = self.reordenar(pregunta, candidatos)
        if not seleccion:
            return Resultado(
                "Encontré fragmentos parecidos, pero ninguno responde la pregunta.", [], consultas, candidatos, puntajes
            )

        respuesta, invalidas = self.generar(pregunta, seleccion)
        fuentes = [
            {"numero": n, "fuente": c["fuente"], "ubicacion": c["ubicacion"], "id": c["id"]}
            for n, c in enumerate(seleccion, start=1)
        ]
        return Resultado(respuesta, fuentes, consultas, candidatos, puntajes, invalidas)


def describir_modelos() -> str:
    return f"respuesta: {MODELO} | planificación y re-ranking: {MODELO_RAPIDO}"
