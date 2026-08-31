"""
Parte 5: el sitio web local (Flask) donde generás el guion, lo revisás y
aprobás (tu paso manual, nunca automático), y después ves/descargás el
video terminado.

Para arrancarlo: python app.py, y abrís http://127.0.0.1:5000 en tu navegador.
Solo funciona en tu propia compu — nadie más puede entrar.
"""

import json
import shutil
import threading
from pathlib import Path

from flask import Flask, redirect, render_template, request, send_file, url_for

from generar_guion import generar_guion, guardar_borrador
from generar_audio import generar_audio_del_guion
from generar_capas import generar_capas
from armar_video import armar_video
from subir_a_supabase import subir_reel

RAIZ = Path(__file__).parent
app = Flask(__name__)


def ruta_estado(fecha):
    return RAIZ / "video" / fecha / "estado.json"


def leer_estado(fecha):
    archivo = ruta_estado(fecha)
    if not archivo.exists():
        return None
    with open(archivo, encoding="utf-8") as f:
        return json.load(f)


def escribir_estado(fecha, paso, mensaje, error=None):
    carpeta = RAIZ / "video" / fecha
    carpeta.mkdir(parents=True, exist_ok=True)
    with open(carpeta / "estado.json", "w", encoding="utf-8") as f:
        json.dump({"paso": paso, "mensaje": mensaje, "error": error}, f, ensure_ascii=False)


def listar_borradores():
    """Junta todos los guiones generados con su estado (borrador / listo)."""
    items = []
    for archivo in sorted((RAIZ / "borradores").glob("*.json"), reverse=True):
        fecha = archivo.stem
        video_listo = (RAIZ / "video" / fecha / "reel.mp4").exists()
        estado = leer_estado(fecha)
        items.append({
            "fecha": fecha,
            "video_listo": video_listo,
            "procesando": estado is not None and estado["paso"] not in ("listo", "error"),
            "error": estado["mensaje"] if estado and estado["paso"] == "error" else None,
        })
    return items


def pipeline_completo(guion):
    """Corre audio + capas + video. Se llama en un hilo aparte para no
    bloquear la página mientras FFmpeg trabaja (tarda 1-3 minutos)."""
    fecha = guion["fecha"]
    try:
        escribir_estado(fecha, "audio", "Generando la voz narrada...")
        generar_audio_del_guion(guion)

        escribir_estado(fecha, "capas", "Dibujando los textos del video...")
        with open(RAIZ / "audio" / fecha / "timeline.json", encoding="utf-8") as f:
            timeline = json.load(f)
        generar_capas(guion, timeline, RAIZ / "capas" / fecha)

        escribir_estado(fecha, "video", "Armando el video final...")
        armar_video(fecha)

        escribir_estado(fecha, "subiendo", "Subiendo el video a la nube...")
        subir_reel(fecha, guion)

        escribir_estado(fecha, "listo", "Video listo.")
    except Exception as e:
        escribir_estado(fecha, "error", str(e))


@app.route("/")
def inicio():
    return render_template("index.html", borradores=listar_borradores())


@app.route("/generar", methods=["POST"])
def generar():
    guion = generar_guion()
    guardar_borrador(guion)
    return redirect(url_for("revisar", fecha=guion["fecha"]))


@app.route("/revisar/<fecha>")
def revisar(fecha):
    with open(RAIZ / "borradores" / f"{fecha}.json", encoding="utf-8") as f:
        guion = json.load(f)
    return render_template("revisar.html", guion=guion)


@app.route("/aprobar/<fecha>", methods=["POST"])
def aprobar(fecha):
    with open(RAIZ / "borradores" / f"{fecha}.json", encoding="utf-8") as f:
        guion = json.load(f)

    escribir_estado(fecha, "iniciando", "Arrancando...")
    hilo = threading.Thread(target=pipeline_completo, args=(guion,), daemon=True)
    hilo.start()

    return redirect(url_for("procesando", fecha=fecha))


@app.route("/procesando/<fecha>")
def procesando(fecha):
    estado = leer_estado(fecha) or {"paso": "iniciando", "mensaje": "Arrancando..."}
    if estado["paso"] == "listo":
        return redirect(url_for("ver", fecha=fecha))
    return render_template("procesando.html", fecha=fecha, estado=estado)


@app.route("/ver/<fecha>")
def ver(fecha):
    return render_template("ver.html", fecha=fecha)


@app.route("/video/<fecha>")
def video_archivo(fecha):
    return send_file(RAIZ / "video" / fecha / "reel.mp4", mimetype="video/mp4")


@app.route("/descargar/<fecha>")
def descargar(fecha):
    return send_file(
        RAIZ / "video" / fecha / "reel.mp4",
        as_attachment=True,
        download_name=f"quiz_reel_{fecha}.mp4",
    )


@app.route("/borrar/<fecha>", methods=["POST"])
def borrar(fecha):
    """Borra todo lo generado para esa fecha (audio, capas, video y el
    guion) para liberar espacio, una vez que ya descargaste lo que
    necesitabas. No borra nada de otras fechas."""
    for carpeta in [RAIZ / "audio" / fecha, RAIZ / "capas" / fecha, RAIZ / "video" / fecha]:
        shutil.rmtree(carpeta, ignore_errors=True)
    (RAIZ / "borradores" / f"{fecha}.json").unlink(missing_ok=True)
    return redirect(url_for("inicio"))


if __name__ == "__main__":
    # host="0.0.0.0" hace que el sitio también responda a otros dispositivos
    # de tu misma red WiFi (como el celular), no solo a esta computadora.
    app.run(debug=True, port=5000, host="0.0.0.0")
