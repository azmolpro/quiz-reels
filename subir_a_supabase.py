"""Sube el video terminado (y los datos del guion) a Supabase Storage,
para que la galería en Vercel pueda mostrarlos desde cualquier lado."""

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

RAIZ = Path(__file__).parent
BUCKET = "reels"


def _cliente():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))


def _subir_con_reintentos(storage, ruta, datos, content_type, intentos=3):
    for intento in range(1, intentos + 1):
        try:
            storage.upload(ruta, datos, file_options={"content-type": content_type, "upsert": "true"})
            return
        except Exception:
            if intento == intentos:
                raise
            time.sleep(3 * intento)


def subir_reel(fecha, guion):
    cliente = _cliente()
    storage = cliente.storage.from_(BUCKET)

    video_local = RAIZ / "video" / fecha / "reel.mp4"
    with open(video_local, "rb") as f:
        _subir_con_reintentos(storage, f"{fecha}/reel.mp4", f.read(), "video/mp4")

    metadata = {
        "fecha": fecha,
        "encabezado": guion["encabezado"],
        "cierre": guion["cierre"],
        "preguntas": [
            {"pregunta": p["pregunta"], "emoji_tema": p.get("emoji_tema")}
            for p in guion["preguntas"]
        ],
    }
    _subir_con_reintentos(
        storage, f"{fecha}/info.json",
        json.dumps(metadata, ensure_ascii=False).encode("utf-8"),
        "application/json",
    )

    url = storage.get_public_url(f"{fecha}/reel.mp4")

    # Verificamos de verdad que quedó accesible, no solo que la subida no
    # tiró error (una vez nos pasó que "no tiró error" pero tampoco estaba).
    for intento in range(5):
        r = requests.head(url, timeout=10)
        if r.status_code == 200:
            return url
        time.sleep(2)
    raise RuntimeError(f"El video se subió pero no quedó accesible en {url} (status {r.status_code})")


def borrar_reel(fecha):
    """Borra el video y su info de Supabase (además de los archivos
    locales, que se borran aparte). Así el botón de 'Borrar' limpia todo,
    no solo lo que está en tu compu."""
    cliente = _cliente()
    storage = cliente.storage.from_(BUCKET)
    storage.remove([f"{fecha}/reel.mp4", f"{fecha}/info.json"])
