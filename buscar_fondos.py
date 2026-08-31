"""Busca videos verticales de galaxia/espacio en Pexels y guarda:
   - las miniaturas (JPG chico) para armar una galería de elección
   - un JSON con los datos de cada video candidato (para descargar el elegido después)
No descarga ningún video completo todavía (para cuidar tus datos móviles)."""

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

CARPETA = Path("fondos_candidatos")
CARPETA.mkdir(exist_ok=True)

headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
params = {
    "query": "galaxy nebula space stars",
    "orientation": "portrait",
    "size": "medium",
    "per_page": 8,
}

r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=15)
r.raise_for_status()
videos = r.json()["videos"]

candidatos = []
for v in videos:
    archivo_1080 = next((f for f in v["video_files"] if f["width"] == 1080 and f["height"] == 1920), None)
    if not archivo_1080:
        continue

    miniatura_bytes = requests.get(v["image"], timeout=15).content
    ruta_miniatura = CARPETA / f"{v['id']}.jpg"
    ruta_miniatura.write_bytes(miniatura_bytes)

    candidatos.append({
        "id": v["id"],
        "autor": v["user"]["name"],
        "duracion": v["duration"],
        "url_descarga": archivo_1080["link"],
        "tamano_mb": round(archivo_1080["size"] / (1024 * 1024), 1),
        "miniatura": str(ruta_miniatura),
        "pagina": v["url"],
    })

with open(CARPETA / "candidatos.json", "w", encoding="utf-8") as f:
    json.dump(candidatos, f, indent=2, ensure_ascii=False)

print(f"Encontré {len(candidatos)} candidatos con versión 1080x1920:")
for c in candidatos:
    print(f"  #{c['id']}  {c['duracion']}s  {c['tamano_mb']} MB  por {c['autor']}")
