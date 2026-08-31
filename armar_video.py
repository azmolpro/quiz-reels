"""
Parte 4: junta todo lo generado en las partes anteriores en el video final:
  - el fondo animado (en loop, hasta cubrir toda la duración)
  - cada capa de texto, con un fundido de entrada, en su momento exacto
  - el audio narrado
Usa FFmpeg directamente (ya lo tenés instalado desde el Paso 1).
"""

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).parent

_FFMPEG_BIN = Path(r"C:\Users\azmol\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin")
FFMPEG = str(_FFMPEG_BIN / "ffmpeg.exe")


def armar_video(fecha, imagen_fondo="fondos/fondo_galaxia_fijo.png"):
    carpeta_audio = RAIZ / "audio" / fecha
    carpeta_capas = RAIZ / "capas" / fecha
    carpeta_salida = RAIZ / "video" / fecha
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    with open(carpeta_audio / "timeline.json", encoding="utf-8") as f:
        timeline = json.load(f)
    with open(carpeta_capas / "capas.json", encoding="utf-8") as f:
        capas = json.load(f)

    duracion_total = timeline[-1]["fin"]
    audio_narracion = carpeta_audio / "narracion.mp3"
    salida = carpeta_salida / "reel.mp4"

    # --- Armamos los argumentos de entrada ---
    args = [FFMPEG, "-y"]
    # input 0: fondo fijo (imagen de galaxia), en loop durante toda la duración
    args += ["-loop", "1", "-framerate", "30", "-i", str(RAIZ / imagen_fondo)]
    for capa in capas:
        args += ["-loop", "1", "-i", capa["archivo"]]  # inputs 1..N: capas de texto
    args += ["-i", str(audio_narracion)]  # último input: audio

    # --- Armamos el filtro: fondo + cada capa apareciendo con un fundido suave ---
    filtro = ["[0:v]scale=1080:1920,setsar=1[bg]"]
    etiqueta_previa = "bg"
    duracion_fundido = 0.35
    for i, capa in enumerate(capas, start=1):
        etiqueta_capa = f"c{i}"
        etiqueta_nueva = f"v{i}"
        filtro.append(
            f"[{i}:v]fade=t=in:st={capa['inicio']}:d={duracion_fundido}:alpha=1[{etiqueta_capa}]"
        )
        filtro.append(
            f"[{etiqueta_previa}][{etiqueta_capa}]overlay=0:0:enable='between(t,{capa['inicio']},{capa['fin']})'[{etiqueta_nueva}]"
        )
        etiqueta_previa = etiqueta_nueva

    args += ["-filter_complex", ";".join(filtro)]
    args += ["-map", f"[{etiqueta_previa}]"]
    args += ["-map", f"{len(capas) + 1}:a"]
    args += ["-t", str(duracion_total)]
    args += ["-c:v", "libx264", "-preset", "faster", "-crf", "27", "-pix_fmt", "yuv420p", "-r", "30"]
    args += ["-c:a", "aac", "-b:a", "160k"]
    args += [str(salida)]

    print(f"Armando video de {duracion_total:.1f}s con {len(capas)} capas...")
    resultado = subprocess.run(args, capture_output=True, text=True)

    if resultado.returncode != 0:
        print("ERROR de FFmpeg:")
        print(resultado.stderr[-3000:])
        raise SystemExit(1)

    print(f"\nVideo final: {salida}")
    return salida


if __name__ == "__main__":
    fecha = sys.argv[1] if len(sys.argv) > 1 else "2026-08-28"
    armar_video(fecha)
