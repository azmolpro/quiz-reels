"""
Parte 4: junta todo lo generado en las partes anteriores en el video final:
  - el fondo fijo (imagen de galaxia)
  - cada capa de texto, en su momento exacto
  - el audio narrado
Usa FFmpeg directamente (ya lo tenés instalado desde el Paso 1).

Lo armamos POR PARTES (un segmento de video corto por cada capa, después
unidos) en vez de un solo comando gigante con las 7 capas juntas. Además,
el fondo y cada capa se COMBINAN CON PYTHON (Pillow) en una sola imagen
plana ANTES de pasársela a FFmpeg — así FFmpeg nunca tiene que mezclar dos
imágenes ni aplicar transiciones por su cuenta, que es lo que más memoria
usa. Todo esto es importante en un servidor con poca RAM (como el plan
gratis de Render, 512 MB): probamos varias formas y esta es la que más
liviana resultó — medimos con datos reales, no a ojo.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

from rutas_sistema import ruta_ffmpeg

RAIZ = Path(__file__).parent
FFMPEG = ruta_ffmpeg()


def _memoria_cgroup_mb():
    """Lee cuánta memoria está usando TODO el contenedor (no solo Python),
    que es lo que decide si el servidor se queda sin memoria. Solo
    funciona en Linux (Render); en Windows devuelve None sin romper nada."""
    for ruta in ("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory/memory.usage_in_bytes"):
        try:
            with open(ruta) as f:
                return int(f.read().strip()) / (1024 * 1024)
        except (FileNotFoundError, ValueError):
            continue
    return None


def _log_memoria(etiqueta):
    mb = _memoria_cgroup_mb()
    if mb is not None:
        print(f"[memoria] {etiqueta}: {mb:.0f} MB", flush=True)


def _correr(args, etiqueta=""):
    """Corre un comando y, si podemos medir memoria (Linux), va anotando
    el PICO de memoria del contenedor mientras el proceso corre.

    Importante: la salida de FFmpeg se manda a un archivo temporal, NUNCA
    a un pipe sin leer — si el pipe se llena (FFmpeg escribe mucho texto
    de progreso) el proceso se queda trabado esperando para siempre."""
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as salida_log:
        proceso = subprocess.Popen(args, stdout=salida_log, stderr=subprocess.STDOUT, text=True)

        pico_mb = _memoria_cgroup_mb()
        while proceso.poll() is None:
            actual = _memoria_cgroup_mb()
            if actual is not None and (pico_mb is None or actual > pico_mb):
                pico_mb = actual
            try:
                proceso.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass

        if etiqueta and pico_mb is not None:
            print(f"[memoria] pico durante {etiqueta}: {pico_mb:.0f} MB", flush=True)

        if proceso.returncode != 0:
            salida_log.seek(0)
            texto = salida_log.read()
            print("ERROR de FFmpeg:")
            print(texto[-3000:])
            raise SystemExit(1)


def _componer_frame_plano(imagen_fondo, capa_archivo, salida_png):
    """Combina el fondo + la capa de texto en UNA sola imagen plana, con
    Pillow (no con FFmpeg). Así FFmpeg solo tiene que loopear una imagen
    ya lista, en vez de mezclar dos y aplicarles filtros — mucho más
    liviano en memoria."""
    fondo = Image.open(imagen_fondo).convert("RGBA")
    if fondo.size != (1080, 1920):
        fondo = fondo.resize((1080, 1920))

    if capa_archivo:
        capa = Image.open(capa_archivo).convert("RGBA")
        compuesto = Image.alpha_composite(fondo, capa)
    else:
        compuesto = fondo

    compuesto.convert("RGB").save(salida_png)


def _armar_segmento(imagen_plana, duracion, salida, etiqueta=""):
    """Arma un tramo corto de video a partir de UNA imagen ya compuesta.
    Sin audio (se agrega al final, una sola vez)."""
    args = [
        FFMPEG, "-y", "-loop", "1", "-framerate", "30", "-i", str(imagen_plana),
        "-t", str(duracion),
        # preset "ultrafast" + threads=1 + sin b-frames/refs extra: usa
        # mucha menos memoria que "faster" (clave para el límite de
        # 512 MB de Render free tier). El archivo pesa un poco más, pero
        # sigue siendo chico.
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
        "-crf", "27", "-refs", "1", "-bf", "0", "-threads", "1",
        "-pix_fmt", "yuv420p", "-r", "30",
        str(salida),
    ]
    _correr(args, etiqueta=etiqueta or "segmento")


def armar_video(fecha, imagen_fondo="fondos/fondo_galaxia_fijo.png"):
    carpeta_audio = RAIZ / "audio" / fecha
    carpeta_capas = RAIZ / "capas" / fecha
    carpeta_salida = RAIZ / "video" / fecha
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    carpeta_temp = carpeta_salida / "_segmentos_temp"
    carpeta_temp.mkdir(exist_ok=True)

    with open(carpeta_audio / "timeline.json", encoding="utf-8") as f:
        timeline = json.load(f)
    with open(carpeta_capas / "capas.json", encoding="utf-8") as f:
        capas = json.load(f)

    duracion_total = timeline[-1]["fin"]
    audio_narracion = carpeta_audio / "narracion.mp3"
    salida = carpeta_salida / "reel.mp4"
    ruta_imagen_fondo = RAIZ / imagen_fondo

    print(f"Armando video de {duracion_total:.1f}s en {len(capas)} segmentos...")

    segmentos = []

    # Tramo inicial (antes de que aparezca la primera capa, ej. mientras se
    # dice el encabezado): solo fondo, sin overlay.
    primer_inicio = capas[0]["inicio"] if capas else duracion_total
    if primer_inicio > 0:
        frame_png = carpeta_temp / "frame_00_intro.png"
        _componer_frame_plano(ruta_imagen_fondo, None, frame_png)
        archivo = carpeta_temp / "seg_00_intro.mp4"
        _armar_segmento(frame_png, primer_inicio, archivo, etiqueta="intro")
        segmentos.append(archivo)

    for i, capa in enumerate(capas, start=1):
        duracion = capa["fin"] - capa["inicio"]
        frame_png = carpeta_temp / f"frame_{i:02d}.png"
        _componer_frame_plano(ruta_imagen_fondo, capa["archivo"], frame_png)
        archivo = carpeta_temp / f"seg_{i:02d}.mp4"
        _armar_segmento(frame_png, duracion, archivo, etiqueta=f"segmento {i}")
        segmentos.append(archivo)
        print(f"  Segmento {i}/{len(capas)} listo.")

    # --- Unimos todos los segmentos (rápido: solo copia, no recodifica) ---
    lista_txt = carpeta_temp / "lista.txt"
    with open(lista_txt, "w", encoding="utf-8") as f:
        for seg in segmentos:
            f.write(f"file '{seg.resolve()}'\n")

    video_sin_audio = carpeta_temp / "sin_audio.mp4"
    _correr([
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lista_txt),
        "-c", "copy", str(video_sin_audio),
    ], etiqueta="concat")

    # --- Agregamos el audio narrado (una sola vez, al final) ---
    _correr([
        FFMPEG, "-y", "-i", str(video_sin_audio), "-i", str(audio_narracion),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        "-t", str(duracion_total),
        str(salida),
    ], etiqueta="mux audio")

    shutil.rmtree(carpeta_temp, ignore_errors=True)

    print(f"\nVideo final: {salida}")
    return salida


if __name__ == "__main__":
    fecha = sys.argv[1] if len(sys.argv) > 1 else "2026-08-28"
    armar_video(fecha)
