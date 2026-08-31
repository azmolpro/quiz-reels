"""Genera el fondo del video: un degradado pastel con un par de manchas de
color que se desplazan MUY lento y en loop perfecto (nada de parpadeos ni
cortes). Todo generado localmente con PIL, sin descargar nada."""

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ANCHO, ALTO = 1080, 1920
RAIZ = Path(__file__).parent

_FFMPEG_BIN = Path(r"C:\Users\azmol\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin")
FFMPEG = str(_FFMPEG_BIN / "ffmpeg.exe")

# Colores pastel, de la misma paleta que las tarjetas del quiz
STOP_A = np.array([238, 234, 255])   # lavanda pastel
STOP_B = np.array([255, 234, 244])   # rosa pastel
STOP_C = np.array([225, 241, 255])   # celeste pastel

MARGEN_MOVIMIENTO = 160  # cuánto se desplazan las manchas (px), sutil
CANVAS_MANCHAS = (ANCHO + MARGEN_MOVIMIENTO * 2, ALTO + MARGEN_MOVIMIENTO * 2)


def generar_gradiente():
    y, x = np.mgrid[0:ALTO, 0:ANCHO]
    t = (x / ANCHO + y / ALTO) / 2

    t3 = np.clip(t * 2, 0, 1)
    color = STOP_A[None, None, :] * (1 - t3[..., None]) + STOP_B[None, None, :] * t3[..., None]

    t3b = np.clip(t * 2 - 1, 0, 1)
    color2 = STOP_B[None, None, :] * (1 - t3b[..., None]) + STOP_C[None, None, :] * t3b[..., None]

    mezcla = np.where(t[..., None] < 0.5, color, color2).astype(np.uint8)
    return Image.fromarray(mezcla, mode="RGB")


def generar_capa_manchas():
    """Dibuja las manchas de color una sola vez, en un lienzo más grande que
    el frame final, para poder 'pasear' una ventana de recorte sobre ellas."""
    capa = Image.new("RGBA", CANVAS_MANCHAS, (0, 0, 0, 0))
    draw = ImageDraw.Draw(capa)

    cx, cy = CANVAS_MANCHAS[0] / 2, CANVAS_MANCHAS[1] / 2
    draw.ellipse((cx - 650, cy - 950, cx + 0, cy - 400), fill=(190, 170, 255, 75))
    draw.ellipse((cx + 100, cy + 550, cx + 800, cy + 1200), fill=(255, 190, 220, 75))
    draw.ellipse((cx - 700, cy + 450, cx - 50, cy + 1050), fill=(170, 210, 255, 65))

    return capa.filter(ImageFilter.GaussianBlur(180))


def generar_frames(n_frames, carpeta_frames):
    carpeta_frames.mkdir(parents=True, exist_ok=True)
    gradiente = generar_gradiente().convert("RGBA")
    manchas = generar_capa_manchas()

    for i in range(n_frames):
        angulo = 2 * math.pi * i / n_frames  # una vuelta completa = loop perfecto
        dx = MARGEN_MOVIMIENTO + MARGEN_MOVIMIENTO * math.cos(angulo)
        dy = MARGEN_MOVIMIENTO + MARGEN_MOVIMIENTO * math.sin(angulo)

        recorte = manchas.crop((dx, dy, dx + ANCHO, dy + ALTO))
        frame = Image.alpha_composite(gradiente, recorte).convert("RGB")
        frame.save(carpeta_frames / f"frame_{i:04d}.png")


def armar_video_loop(carpeta_frames, salida, fps=30):
    subprocess.run([
        FFMPEG, "-y",
        "-framerate", str(fps),
        "-i", str(carpeta_frames / "frame_%04d.png"),
        "-c:v", "libx264", "-preset", "faster", "-crf", "20", "-pix_fmt", "yuv420p",
        str(salida),
    ], check=True, capture_output=True)


if __name__ == "__main__":
    carpeta_frames = RAIZ / "fondos" / "_frames_temp"
    salida = RAIZ / "fondos" / "fondo_animado.mp4"

    n_frames = 240  # 8 segundos a 30fps, loop lento y suave
    print(f"Generando {n_frames} frames...")
    generar_frames(n_frames, carpeta_frames)

    print("Armando el video en loop...")
    armar_video_loop(carpeta_frames, salida)

    for f in carpeta_frames.glob("*.png"):
        f.unlink()
    carpeta_frames.rmdir()

    print(f"Listo: {salida}")
