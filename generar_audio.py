"""
Parte 2: convierte un guion (JSON de generar_guion.py) en el audio narrado
del reel, usando Edge-TTS (voz gratis). También arma una "línea de tiempo"
(timeline.json) con el inicio/fin de cada parte, para que más adelante el
video pueda sincronizar los textos en pantalla con lo que se está diciendo.
"""

import asyncio
import json
import re
import subprocess
from pathlib import Path

import edge_tts

from rutas_sistema import ruta_ffmpeg, ruta_ffprobe

VOZ = "es-ES-ElviraNeural"
PAUSA_SUSPENSO_SEGUNDOS = 1.6
CARPETA_AUDIO = Path("audio")

FFMPEG = ruta_ffmpeg()
FFPROBE = ruta_ffprobe()

LETRAS = ["A", "B", "C"]

EMOJI_REGEX = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)


def limpiar_para_voz(texto):
    """Saca emojis (la IA de voz no los lee bien) y espacios de sobra."""
    sin_emoji = EMOJI_REGEX.sub("", texto)
    return re.sub(r"\s+", " ", sin_emoji).strip()


def construir_guion_hablado(guion):
    """Convierte el guion en una lista ordenada de 'segmentos': cada uno es
    algo que se dice (voz) o un silencio (pausa de suspenso)."""
    segmentos = []

    segmentos.append({"tipo": "voz", "rol": "encabezado", "texto": limpiar_para_voz(guion["encabezado"])})

    for i, p in enumerate(guion["preguntas"], start=1):
        opciones_habladas = ", ".join(
            f"opción {LETRAS[j]}: {op}" for j, op in enumerate(p["opciones"])
        )
        texto_pregunta = f"Pregunta {i}. {p['pregunta']} {opciones_habladas}."
        segmentos.append({"tipo": "voz", "rol": f"pregunta_{i}", "texto": limpiar_para_voz(texto_pregunta)})

        segmentos.append({"tipo": "silencio", "rol": f"pausa_{i}", "duracion": PAUSA_SUSPENSO_SEGUNDOS})

        letra_correcta = LETRAS[p["opciones"].index(p["respuesta_correcta"])]
        texto_revelacion = f"¡Era la opción {letra_correcta}! {p['explicacion']}"
        segmentos.append({"tipo": "voz", "rol": f"revelacion_{i}", "texto": limpiar_para_voz(texto_revelacion)})

    segmentos.append({"tipo": "voz", "rol": "cierre", "texto": limpiar_para_voz(guion["cierre"])})

    return segmentos


async def sintetizar_voz(texto, archivo_salida):
    comunicador = edge_tts.Communicate(texto, VOZ)
    await comunicador.save(str(archivo_salida))


def duracion_segundos(archivo_audio):
    resultado = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(archivo_audio)],
        capture_output=True, text=True, check=True,
    )
    return float(resultado.stdout.strip())


def generar_silencio(duracion, archivo_salida):
    subprocess.run(
        [FFMPEG, "-y", "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono",
         "-t", str(duracion), "-q:a", "9", str(archivo_salida)],
        capture_output=True, check=True,
    )


def concatenar_audios(lista_archivos, archivo_salida, carpeta):
    lista_txt = carpeta / "lista_concat.txt"
    with open(lista_txt, "w", encoding="utf-8") as f:
        for archivo in lista_archivos:
            f.write(f"file '{archivo.name}'\n")

    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lista_txt),
         "-c", "copy", str(archivo_salida)],
        capture_output=True, check=True,
    )


def generar_audio_del_guion(guion):
    carpeta = CARPETA_AUDIO / guion["fecha"]
    carpeta.mkdir(parents=True, exist_ok=True)

    segmentos = construir_guion_hablado(guion)
    archivos = []
    timeline = []
    tiempo_actual = 0.0

    for i, seg in enumerate(segmentos):
        archivo = carpeta / f"{i:02d}_{seg['rol']}.mp3"

        if seg["tipo"] == "voz":
            print(f"Generando voz: {seg['rol']} -> \"{seg['texto'][:60]}...\"")
            asyncio.run(sintetizar_voz(seg["texto"], archivo))
        else:
            print(f"Generando silencio: {seg['rol']} ({seg['duracion']}s)")
            generar_silencio(seg["duracion"], archivo)

        dur = duracion_segundos(archivo)
        timeline.append({
            "rol": seg["rol"],
            "inicio": round(tiempo_actual, 2),
            "fin": round(tiempo_actual + dur, 2),
        })
        tiempo_actual += dur
        archivos.append(archivo)

    archivo_final = carpeta / "narracion.mp3"
    concatenar_audios(archivos, archivo_final, carpeta)

    archivo_timeline = carpeta / "timeline.json"
    with open(archivo_timeline, "w", encoding="utf-8") as f:
        json.dump(timeline, f, indent=2, ensure_ascii=False)

    return archivo_final, archivo_timeline, tiempo_actual


if __name__ == "__main__":
    import sys

    ruta_guion = sys.argv[1] if len(sys.argv) > 1 else "borradores/2026-08-27.json"
    with open(ruta_guion, encoding="utf-8") as f:
        guion = json.load(f)

    audio, timeline, duracion_total = generar_audio_del_guion(guion)

    print(f"\nAudio final: {audio}")
    print(f"Timeline: {timeline}")
    print(f"Duración total: {duracion_total:.1f} segundos (objetivo: 60-90s)")
