"""
Lleva un registro de qué hechos (por su fuente de Wikipedia) ya se usaron
en reels anteriores, para no repetir la misma pregunta en dos reels
distintos. Se guarda en Supabase (no en el disco local) porque en Render
el disco se borra en cada redeploy — necesitamos que esto sea permanente.
"""

import json
import os

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

BUCKET = "reels"
RUTA_HISTORIAL = "_historial/fuentes_usadas.json"


def _cliente():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))


def cargar_fuentes_usadas():
    """Devuelve el conjunto de URLs de fuente ya usadas en reels anteriores.
    Si todavía no existe el historial (primera vez), devuelve vacío."""
    try:
        cliente = _cliente()
        datos = cliente.storage.from_(BUCKET).download(RUTA_HISTORIAL)
        return set(json.loads(datos.decode("utf-8")))
    except Exception:
        return set()


def agregar_fuentes_usadas(nuevas_fuentes):
    """Agrega fuentes al historial y lo guarda. No borra nada, solo suma."""
    actuales = cargar_fuentes_usadas()
    actuales.update(nuevas_fuentes)

    cliente = _cliente()
    cliente.storage.from_(BUCKET).upload(
        RUTA_HISTORIAL,
        json.dumps(sorted(actuales), ensure_ascii=False).encode("utf-8"),
        file_options={"content-type": "application/json", "upsert": "true"},
    )
