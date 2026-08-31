import sys
from pathlib import Path
from PIL import Image

fecha = sys.argv[2] if len(sys.argv) > 2 else "2026-08-28"
carpeta = Path("capas") / fecha
fondo = Image.open("fondos/fondo_galaxia_fijo.png").convert("RGBA").resize((1080, 1920))

nombre = sys.argv[1] if len(sys.argv) > 1 else "01a_pregunta.png"
capa = Image.open(carpeta / nombre).convert("RGBA")

compuesto = Image.alpha_composite(fondo, capa).convert("RGB")
salida = carpeta / f"preview_{nombre}"
compuesto.save(salida)
print("Guardado:", salida)
