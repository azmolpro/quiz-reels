"""
Encuentra los programas y fuentes que la app necesita, sin importar si
corre en tu PC con Windows o en un servidor con Linux (como Render).
Primero busca en el PATH del sistema (lo normal en Linux); si no lo
encuentra, prueba rutas típicas de Windows como respaldo.
"""

import shutil
from pathlib import Path

_FFMPEG_WINDOWS = r"C:\Users\azmol\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"
_FFPROBE_WINDOWS = r"C:\Users\azmol\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffprobe.exe"

_FUENTES_EMOJI = [
    r"C:\Windows\Fonts\seguiemj.ttf",                       # Windows
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",     # Linux (Debian/Ubuntu, paquete fonts-noto-color-emoji)
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
]


def _binario(nombre, respaldo_windows):
    encontrado = shutil.which(nombre)
    if encontrado:
        return encontrado
    if Path(respaldo_windows).exists():
        return respaldo_windows
    raise FileNotFoundError(
        f"No encontré '{nombre}'. Instalalo o agregalo al PATH del sistema."
    )


def ruta_ffmpeg():
    return _binario("ffmpeg", _FFMPEG_WINDOWS)


def ruta_ffprobe():
    return _binario("ffprobe", _FFPROBE_WINDOWS)


def ruta_fuente_emoji():
    for candidata in _FUENTES_EMOJI:
        if Path(candidata).exists():
            return candidata
    raise FileNotFoundError(
        "No encontré una fuente de emoji a color instalada. "
        "En Linux: apt-get install -y fonts-noto-color-emoji"
    )
