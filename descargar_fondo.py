"""Descarga el video de fondo elegido (1080x1920) desde Pexels."""

import json
import sys
from pathlib import Path

import requests

CARPETA_CANDIDATOS = Path("fondos_candidatos")
CARPETA_FONDOS = Path("fondos")
CARPETA_FONDOS.mkdir(exist_ok=True)


def descargar_fondo(id_video):
    candidatos = json.loads((CARPETA_CANDIDATOS / "candidatos.json").read_text(encoding="utf-8"))
    elegido = next((c for c in candidatos if c["id"] == id_video), None)
    if not elegido:
        raise SystemExit(f"No encontré el candidato #{id_video} en candidatos.json")

    print(f"Descargando fondo #{id_video} ({elegido['tamano_mb']} MB)...")
    r = requests.get(elegido["url_descarga"], timeout=120, stream=True)
    r.raise_for_status()

    destino = CARPETA_FONDOS / f"{id_video}.mp4"
    with open(destino, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 256):
            f.write(chunk)

    print(f"Guardado en: {destino}")
    return destino


if __name__ == "__main__":
    id_video = int(sys.argv[1]) if len(sys.argv) > 1 else 35288809
    descargar_fondo(id_video)
