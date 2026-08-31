"""
Parte 1: genera el guion de un reel de quiz a partir de datos REALES y
verificados (efemérides de Wikipedia del día de hoy).

Gemini se usa ÚNICAMENTE para elegir cuáles de los datos reales son más
interesantes para trivia y redactar la pregunta/opciones/explicación de cada
uno (en un solo pedido, para cuidar la cuota gratuita). Nunca se le pide que
invente hechos, y la fuente (URL) siempre es la real de Wikipedia, puesta
por nuestro código según el índice que devuelve la IA, no una fuente que
la IA escriba por su cuenta.
"""

import json
import os
import time
from datetime import date

import requests
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ClientError, ServerError

load_dotenv()

WIKIPEDIA_HEADERS = {
    "User-Agent": "QuizReelsApp/0.1 (proyecto educativo personal; mlubservice@gmail.com)"
}

# Probamos estos modelos en orden. Cada uno tiene su propia cuota gratuita
# separada, así que si el mejor se queda sin cuota (o está caído), pasamos
# automáticamente al siguiente en vez de cortar la generación del día.
MODELOS_GEMINI = ["gemini-3.6-flash", "gemini-3-flash-preview", "gemini-3.5-flash-lite"]


def _generar_con_reintentos(cliente, **kwargs):
    """Prueba cada modelo de la lista. Para cada uno, reintenta unas pocas
    veces si el servidor está temporalmente saturado (503) antes de pasar
    al siguiente modelo. Si se quedó sin cuota (429), pasa al siguiente
    modelo directamente, sin esperar."""
    ultimo_error = None
    for modelo in MODELOS_GEMINI:
        intentos = 3
        for intento in range(1, intentos + 1):
            try:
                return cliente.models.generate_content(model=modelo, **kwargs)
            except ServerError as e:
                ultimo_error = e
                if intento == intentos:
                    break
                time.sleep(5 * intento)
            except ClientError as e:
                ultimo_error = e
                break  # sin cuota o modelo no disponible: probamos el siguiente modelo ya
    raise ultimo_error


def traer_datos_reales(tipo, mes, dia):
    """Trae hechos reales de Wikipedia para una fecha. tipo: 'events' o 'births'."""
    url = f"https://es.wikipedia.org/api/rest_v1/feed/onthisday/{tipo}/{mes}/{dia}"
    r = requests.get(url, headers=WIKIPEDIA_HEADERS, timeout=15)
    r.raise_for_status()
    items = r.json().get(tipo, [])

    resultado = []
    for item in items:
        paginas = item.get("pages", [])
        fuente = paginas[0]["content_urls"]["desktop"]["page"] if paginas else None
        if not fuente:
            continue
        resultado.append({
            "anio": item.get("year"),
            "texto": item.get("text"),
            "fuente": fuente,
        })
    return resultado


def elegir_y_redactar(cliente, datos_reales, cantidad=3):
    """Un ÚNICO pedido a Gemini que hace las dos cosas: ELIGE los mejores datos reales
    de la lista, y REDACTA la pregunta/opciones/explicación de cada uno. Nunca inventa
    hechos nuevos: solo puede usar el texto de los datos que le pasamos, cada uno con su
    número (después nosotros pegamos la fuente real según ese número, no la que diga la IA)."""
    lista_numerada = "\n".join(
        f"{i}. (Año {d['anio']}) {d['texto']}" for i, d in enumerate(datos_reales)
    )

    prompt = f"""Tenés una lista de hechos REALES y verificados, cada uno con un número.

PASO 1 — ELEGIR: elegí los {cantidad} hechos que MÁS le van a volar la cabeza a un adolescente
de 12 a 17 años, para un quiz viral en redes sociales (estilo "no lo vas a creer"). El criterio real
es UNO SOLO: ¿esto le sacaría un "¿¿QUÉ??" a un pibe de 15 años HOY, en 2026? Si tenés que explicarle
primero quién es alguien o por qué importa, no sirve. Priorizá SIEMPRE, en este orden:
1) animales (habilidades increíbles, récords, curiosidades del cuerpo animal),
2) espacio y ciencia loca que suena a ciencia ficción pero es real,
3) récords extremos/Guinness de cosas físicas o naturales (el más grande, rápido, raro del mundo),
4) cuerpo humano, tecnología, gaming, internet, inventos que se usan en la vida diaria de HOY,
5) datos históricos SOLO si tienen un giro tan loco que sorprendería a cualquiera, sin importar la edad.
EVITÁ especialmente trivia de la industria del entretenimiento de hace décadas (charts de música,
premios, ventas de discos, récords de Billboard, cine viejo) — son datos de "libro de trivia para
adultos", no algo que un adolescente de hoy reconozca o le importe, aunque técnicamente sea un récord.
DESCARTÁ SIEMPRE, sin excepción (el público son menores de edad): drogas, alcohol, tabaco,
contenido sexual o romántico, violencia gráfica, autolesión, apuestas, y también, salvo que sea
verdaderamente asombroso: política, elecciones, gobiernos, diplomacia, guerras, ejércitos, armas,
atentados, desastres, muertes, funerales, economía, empresas, bolsa, religión institucional,
trámites o nombramientos.

PASO 2 — REDACTAR: para cada uno de los {cantidad} elegidos, usando SOLO la información de ese
hecho (no agregues datos que no estén ahí), armá:
- "pregunta": con gancho, tipo desafío ("¿Te animás a adivinar...", "¿Sabés cuál..."), nunca como
  enunciado de examen aburrido. Debe poder responderse solo con la info del hecho.
- "opciones": 3 opciones, 1 correcta (el dato real) y 2 incorrectas pero creíbles (inventadas por
  vos como distractores).
- "respuesta_correcta": el texto exacto de la opción correcta, igual a como aparece en "opciones".
- "explicacion": UNA sola frase (máx. 18 palabras), directa, tono "posta que esto es una locura",
  nunca repitas "la respuesta correcta es".
- "emoji_tema": UN emoji que represente el tema (ej: 🐙 pulpo, 🚀 espacial, 🎮 videojuegos).
- "indice_dato": el número de la lista de donde sacaste este hecho.

Todo en español, tono joven, entusiasta y cercano, nada acartonado. Esto se lee en voz alta en un
video de 60-90 segundos: cada palabra cuenta, sé breve en todo.

Respondé ÚNICAMENTE con este JSON:
{{"preguntas": [
  {{"indice_dato": 0, "pregunta": "...", "opciones": ["...","...","..."],
    "respuesta_correcta": "...", "explicacion": "...", "emoji_tema": "..."}}
]}}

Lista:
{lista_numerada}
"""

    respuesta = _generar_con_reintentos(
        cliente,
        contents=prompt,
        config={"response_mime_type": "application/json"},
    )

    preguntas = json.loads(respuesta.text)["preguntas"]
    for p in preguntas:
        p["fuente"] = datos_reales[p["indice_dato"]]["fuente"]
        del p["indice_dato"]
        # A veces la IA agrega espacios de más; los sacamos para que las
        # comparaciones de "cuál opción es la correcta" no fallen nunca.
        p["pregunta"] = p["pregunta"].strip()
        p["opciones"] = [o.strip() for o in p["opciones"]]
        p["respuesta_correcta"] = p["respuesta_correcta"].strip()
        p["explicacion"] = p["explicacion"].strip()
    return preguntas


def generar_guion(fecha=None):
    """Arma el guion completo del día: encabezado + 3 preguntas con fuente + cierre."""
    fecha = fecha or date.today()
    mes, dia = f"{fecha.month:02d}", f"{fecha.day:02d}"
    cliente = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    datos = (
        traer_datos_reales("events", mes, dia)
        + traer_datos_reales("births", mes, dia)
        + traer_datos_reales("holidays", mes, dia)
    )
    preguntas = elegir_y_redactar(cliente, datos, cantidad=3)

    guion = {
        "fecha": fecha.isoformat(),
        "encabezado": "🧠 ¿Adivinás cuál? 🔍",
        "preguntas": preguntas,
        "cierre": "Seguime para más datos curiosos que seguro no sabías 🤯",
    }

    return guion


def guardar_borrador(guion):
    nombre_archivo = f"borradores/{guion['fecha']}.json"
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        json.dump(guion, f, indent=2, ensure_ascii=False)
    return nombre_archivo


def mostrar_para_revision(guion):
    print("\n" + "=" * 70)
    print(guion["encabezado"])
    print("=" * 70)
    for i, p in enumerate(guion["preguntas"], start=1):
        print(f"\nPregunta {i}: {p['pregunta']}")
        for opcion in p["opciones"]:
            marca = "✅" if opcion == p["respuesta_correcta"] else "  "
            print(f"  {marca} {opcion}")
        print(f"  Por qué: {p['explicacion']}")
        print(f"  Fuente: {p['fuente']}")
    print(f"\nCierre: {guion['cierre']}")
    print("=" * 70)


if __name__ == "__main__":
    guion = generar_guion()
    mostrar_para_revision(guion)
    archivo = guardar_borrador(guion)
    print(f"\nGuardado en: {archivo}")
    print("Revisalo. Si algo no es correcto o no te convence, avisame antes de seguir.")
