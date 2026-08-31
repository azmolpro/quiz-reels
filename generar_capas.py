"""
Parte 3: dibuja los textos del quiz (encabezado, pregunta, opciones, la
correcta en verde, explicación, cierre) como imágenes PNG transparentes de
1080x1920 — una por cada momento del video (según timeline.json de la
Parte 2). En la Parte 4 estas imágenes se van a superponer al video de
fondo, cada una activa solo durante su ventana de tiempo.
"""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

from rutas_sistema import ruta_fuente_emoji

RAIZ = Path(__file__).parent
ANCHO, ALTO = 1080, 1920

# --- Paleta clara, tipo "juego de trivia" (fondo blanco, colores sólidos) ---
BLANCO = (255, 255, 255, 255)
PANEL_PREGUNTA = (241, 238, 254, 255)   # lavanda muy claro
PANEL_EXPLICACION = (255, 247, 230, 255)  # crema calido
TEXTO = (31, 27, 58, 255)               # indigo oscuro, casi negro
TEXTO_MUTED = (146, 142, 168, 255)
ACENTO = (91, 61, 245, 255)             # violeta vivo
VERDE_CORRECTA = (34, 197, 94, 255)
GRIS_INCORRECTA = (229, 231, 235, 255)
TEXTO_INCORRECTA = (156, 160, 176, 255)

# Un color distinto por opción (A, B, C) sin revelar todavía, estilo Kahoot
COLORES_OPCION = [
    (61, 169, 252, 255),   # azul
    (255, 138, 61, 255),   # naranja
    (255, 61, 119, 255),   # rosa
]

EMOJI_REGEX = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF]+", flags=re.UNICODE)


def cargar_fuentes():
    fredoka_path = str(RAIZ / "fuentes" / "Fredoka.ttf")
    karla_path = str(RAIZ / "fuentes" / "Karla.ttf")
    emoji_path = ruta_fuente_emoji()

    def fredoka(tam, peso=700):
        f = ImageFont.truetype(fredoka_path, tam)
        f.set_variation_by_axes([peso, 100])
        return f

    def karla(tam, peso=400):
        f = ImageFont.truetype(karla_path, tam)
        f.set_variation_by_axes([peso])
        return f

    def emoji(tam):
        return ImageFont.truetype(emoji_path, tam)

    return fredoka, karla, emoji


def envolver_texto(draw, texto, font, ancho_max):
    palabras = texto.split()
    lineas, actual = [], ""
    for palabra in palabras:
        prueba = f"{actual} {palabra}".strip()
        if draw.textlength(prueba, font=font) <= ancho_max:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def dibujar_mixto(draw, xy, texto, font_texto, font_emoji, fill):
    """Dibuja una línea con texto y emoji mezclados, avanzando el cursor X."""
    x, y = xy
    partes = EMOJI_REGEX.split(texto)
    emojis = EMOJI_REGEX.findall(texto)
    trozos = []
    for i, parte in enumerate(partes):
        if parte:
            trozos.append((parte, font_texto, fill, False))
        if i < len(emojis):
            trozos.append((emojis[i], font_emoji, None, True))

    for contenido, font, color, es_emoji in trozos:
        if es_emoji:
            draw.text((x, y), contenido, font=font, embedded_color=True)
        else:
            draw.text((x, y), contenido, font=font, fill=color)
        x += draw.textlength(contenido, font=font)
    return x


def panel_redondeado(draw, box, color, radio=28):
    draw.rounded_rectangle(box, radius=radio, fill=color)


def nuevo_lienzo():
    return Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))


def dibujar_header(img, draw, fredoka, emoji_font):
    texto = "¿Adivinás cuál?"
    tam_fuente = fredoka(52)
    tam_emoji = emoji_font(52)

    ancho_texto = draw.textlength(texto, font=tam_fuente)
    ancho_total = 60 + ancho_texto + 60  # emoji izq + texto + emoji der (aprox)
    caja = ((ANCHO - ancho_total - 80) / 2, 70, (ANCHO + ancho_total + 80) / 2, 170)
    panel_redondeado(draw, caja, ACENTO, radio=50)

    x = caja[0] + 30
    x = dibujar_mixto(draw, (x, 88), "🧠 ", tam_fuente, tam_emoji, BLANCO)
    draw.text((x, 95), texto, font=tam_fuente, fill=BLANCO)
    x += ancho_texto
    dibujar_mixto(draw, (x + 10, 88), " 🔍", tam_fuente, tam_emoji, BLANCO)


def dibujar_sticker_emoji(img, emoji_font, emoji, cx, cy, diametro=150, angulo=-10):
    """Dibuja el emoji temático como una 'stickercita' redonda y un poco
    inclinada, como si estuviera pegada arriba de la tarjeta."""
    tam_lienzo = diametro + 40
    sticker = Image.new("RGBA", (tam_lienzo, tam_lienzo), (0, 0, 0, 0))
    d = ImageDraw.Draw(sticker)
    borde = (tam_lienzo - diametro) // 2
    d.ellipse((borde, borde, borde + diametro, borde + diametro), fill=BLANCO, outline=ACENTO, width=6)

    f_emoji = emoji_font(int(diametro * 0.6))
    bbox = d.textbbox((0, 0), emoji, font=f_emoji)
    ancho_e, alto_e = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((tam_lienzo / 2 - ancho_e / 2 - bbox[0], tam_lienzo / 2 - alto_e / 2 - bbox[1]),
           emoji, font=f_emoji, embedded_color=True)

    sticker = sticker.rotate(angulo, resample=Image.BICUBIC, expand=True)
    img.paste(sticker, (int(cx - sticker.width / 2), int(cy - sticker.height / 2)), sticker)


def dibujar_pregunta(guion_pregunta, numero, total, revelar):
    fredoka, karla, emoji_font = cargar_fuentes()
    img = nuevo_lienzo()
    draw = ImageDraw.Draw(img)

    dibujar_header(img, draw, fredoka, emoji_font)

    margen = 70
    ancho_util = ANCHO - margen * 2

    # --- Contador "Pregunta X de 3" ---
    contador_font = karla(34, 700)
    draw.text((margen, 260), f"PREGUNTA {numero} DE {total}", font=contador_font, fill=ACENTO)

    # --- Panel de la pregunta ---
    pregunta_font = fredoka(56, 600)
    lineas = envolver_texto(draw, guion_pregunta["pregunta"], pregunta_font, ancho_util - 60)
    alto_panel_pregunta = 70 + len(lineas) * 68 + 30
    y_panel = 320
    panel_redondeado(draw, (margen, y_panel, ANCHO - margen, y_panel + alto_panel_pregunta), PANEL_PREGUNTA, radio=32)

    y_texto = y_panel + 40
    for linea in lineas:
        draw.text((margen + 30, y_texto), linea, font=pregunta_font, fill=TEXTO)
        y_texto += 68

    emoji_tema = guion_pregunta.get("emoji_tema")
    if emoji_tema:
        dibujar_sticker_emoji(img, emoji_font, emoji_tema, ANCHO - margen - 60, y_panel, diametro=140)

    # --- Opciones ---
    letras = ["A", "B", "C"]
    y_opcion = y_panel + alto_panel_pregunta + 50
    alto_opcion = 130
    opcion_font = karla(40, 700)
    letra_font = fredoka(44, 700)

    for i, texto_opcion in enumerate(guion_pregunta["opciones"]):
        es_correcta = texto_opcion == guion_pregunta["respuesta_correcta"]
        caja = (margen, y_opcion, ANCHO - margen, y_opcion + alto_opcion)

        if revelar and es_correcta:
            panel_redondeado(draw, caja, VERDE_CORRECTA, radio=26)
            color_texto = BLANCO
        elif revelar:
            panel_redondeado(draw, caja, GRIS_INCORRECTA, radio=26)
            color_texto = TEXTO_INCORRECTA
        else:
            panel_redondeado(draw, caja, COLORES_OPCION[i], radio=26)
            color_texto = BLANCO

        draw.text((margen + 32, y_opcion + 42), letras[i], font=letra_font, fill=color_texto)

        lineas_op = envolver_texto(draw, texto_opcion, opcion_font, ancho_util - 160)
        y_op_texto = y_opcion + (alto_opcion - len(lineas_op) * 48) / 2
        for linea in lineas_op:
            draw.text((margen + 110, y_op_texto), linea, font=opcion_font, fill=color_texto)
            y_op_texto += 48

        if revelar and es_correcta:
            marca_font = emoji_font(48)
            draw.text((ANCHO - margen - 70, y_opcion + 38), "✔️", font=marca_font, embedded_color=True)

        y_opcion += alto_opcion + 22

    # --- Explicación (solo al revelar) ---
    if revelar:
        y_expl = y_opcion + 10
        explicacion_font = karla(38, 400)
        lineas_expl = envolver_texto(draw, guion_pregunta["explicacion"], explicacion_font, ancho_util - 80)
        alto_expl = 70 + len(lineas_expl) * 50 + 50

        panel_redondeado(draw, (margen, y_expl, ANCHO - margen, y_expl + alto_expl), PANEL_EXPLICACION, radio=32)

        etiqueta_font = karla(30, 700)
        etiqueta_emoji_font = emoji_font(30)
        draw.text((margen + 34, y_expl + 24), "💡", font=etiqueta_emoji_font, embedded_color=True)
        draw.text((margen + 34 + 40, y_expl + 26), "POR QUÉ", font=etiqueta_font, fill=ACENTO)

        y_t = y_expl + 70
        for linea in lineas_expl:
            draw.text((margen + 34, y_t), linea, font=explicacion_font, fill=TEXTO)
            y_t += 50

        dominio = urlparse(guion_pregunta["fuente"]).netloc
        fuente_font = karla(26, 400)
        draw.text((margen + 34, y_expl + alto_expl - 44), f"Fuente: {dominio}", font=fuente_font, fill=TEXTO_MUTED)

    return img


def dibujar_cierre(texto_cierre):
    fredoka, karla, emoji_font = cargar_fuentes()
    img = nuevo_lienzo()
    draw = ImageDraw.Draw(img)

    dibujar_header(img, draw, fredoka, emoji_font)

    margen = 90
    cierre_font = fredoka(64, 700)
    texto_limpio = EMOJI_REGEX.sub("", texto_cierre).strip()
    lineas = envolver_texto(draw, texto_limpio, cierre_font, ANCHO - margen * 2)

    alto_bloque = len(lineas) * 78
    y = (ALTO - alto_bloque) / 2

    for linea in lineas:
        ancho_linea = draw.textlength(linea, font=cierre_font)
        draw.text(((ANCHO - ancho_linea) / 2, y), linea, font=cierre_font, fill=ACENTO)
        y += 78

    return img


def generar_capas(guion, timeline, carpeta_salida):
    carpeta_salida = Path(carpeta_salida)
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    total_preguntas = len(guion["preguntas"])
    capas = []

    por_rol = {t["rol"]: t for t in timeline}

    for i, pregunta in enumerate(guion["preguntas"], start=1):
        # Frame sin revelar: cubre "pregunta_i" + "pausa_i" (todo el suspenso)
        inicio = por_rol[f"pregunta_{i}"]["inicio"]
        fin = por_rol[f"pausa_{i}"]["fin"]
        img = dibujar_pregunta(pregunta, i, total_preguntas, revelar=False)
        archivo = carpeta_salida / f"{i:02d}a_pregunta.png"
        img.save(archivo)
        capas.append({"archivo": str(archivo), "inicio": inicio, "fin": fin})

        # Frame revelado: cubre "revelacion_i"
        inicio_r = por_rol[f"revelacion_{i}"]["inicio"]
        fin_r = por_rol[f"revelacion_{i}"]["fin"]
        img_r = dibujar_pregunta(pregunta, i, total_preguntas, revelar=True)
        archivo_r = carpeta_salida / f"{i:02d}b_revelacion.png"
        img_r.save(archivo_r)
        capas.append({"archivo": str(archivo_r), "inicio": inicio_r, "fin": fin_r})

    inicio_c = por_rol["cierre"]["inicio"]
    fin_c = por_rol["cierre"]["fin"]
    img_c = dibujar_cierre(guion["cierre"])
    archivo_c = carpeta_salida / "99_cierre.png"
    img_c.save(archivo_c)
    capas.append({"archivo": str(archivo_c), "inicio": inicio_c, "fin": fin_c})

    with open(carpeta_salida / "capas.json", "w", encoding="utf-8") as f:
        json.dump(capas, f, indent=2, ensure_ascii=False)

    return capas


if __name__ == "__main__":
    import sys
    fecha = sys.argv[1] if len(sys.argv) > 1 else "2026-08-28"

    with open(RAIZ / "borradores" / f"{fecha}.json", encoding="utf-8") as f:
        guion = json.load(f)
    with open(RAIZ / "audio" / fecha / "timeline.json", encoding="utf-8") as f:
        timeline = json.load(f)

    capas = generar_capas(guion, timeline, RAIZ / "capas" / fecha)
    print(f"Generé {len(capas)} capas:")
    for c in capas:
        print(f"  {Path(c['archivo']).name}: {c['inicio']}s -> {c['fin']}s")
