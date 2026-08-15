from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv
import anthropic
import os
import json

load_dotenv()

app = Flask(__name__)
CORS(app)

client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)


# Red de seguridad: si algo falla y nadie lo captura, respondemos JSON (nunca HTML)
@app.errorhandler(Exception)
def error_inesperado(e):
    if isinstance(e, HTTPException):
        return jsonify({"error": e.description}), e.code
    print("Error inesperado:", repr(e))
    return jsonify({"error": "Error interno del servidor. Inténtalo de nuevo."}), 500


@app.route("/menu", methods=["POST"])
def generar_menu():
    # silent=True hace que devuelva None en vez de romperse si no llega JSON válido
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify({"error": "No se recibieron datos válidos"}), 400

    ingredientes = (datos.get("ingredientes") or "").strip()
    fecha_inicio = (datos.get("fechaInicio") or "").strip()

    if not ingredientes:
        return jsonify({"error": "Escribe al menos un ingrediente"}), 400
    if not fecha_inicio:
        return jsonify({"error": "Elige una fecha de inicio"}), 400

    prompt = f"""Tengo estos ingredientes en la nevera: {ingredientes}.
Generame un menu para 7 dias empezando el {fecha_inicio} (formato YYYY-MM-DD, dias consecutivos).
Usa principalmente esos ingredientes.
Responde SOLO con JSON valido, sin texto antes ni despues, con este formato exacto:
{{"dias": [{{"fecha": "YYYY-MM-DD", "Desayuno": "texto corto", "Almuerzo": "texto corto", "Merienda": "texto corto", "Cena": "texto corto"}}]}}
"""

    # Capturamos los fallos de la API de más concreto a más general
    try:
        mensaje = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system="Eres una asistente que genera menús semanales saludables usando principalmente los ingredientes que el usuario tiene en la nevera. Responde siempre en JSON válido, sin texto adicional.",
            messages=[{"role": "user", "content": prompt}]
        )
    except anthropic.AuthenticationError as e:
        print("Error de autenticación con Anthropic:", repr(e))
        return jsonify({"error": "Problema de configuración del servidor: la clave de la API no es válida."}), 500
    except anthropic.PermissionDeniedError as e:
        print("Permiso denegado por Anthropic:", repr(e))
        return jsonify({"error": "La clave de la API no tiene permisos para este modelo."}), 500
    except anthropic.NotFoundError as e:
        print("Modelo no encontrado:", repr(e))
        return jsonify({"error": "El modelo de IA configurado no existe."}), 500
    except anthropic.RateLimitError as e:
        print("Límite de peticiones superado:", repr(e))
        return jsonify({"error": "Se ha superado el límite de peticiones. Espera un momento y vuelve a intentarlo."}), 429
    except anthropic.APIConnectionError as e:
        print("No se pudo conectar con Anthropic:", repr(e))
        return jsonify({"error": "No se pudo conectar con el servicio de IA. Revisa tu conexión e inténtalo de nuevo."}), 503
    except anthropic.APIStatusError as e:
        print("Error devuelto por Anthropic:", e.status_code, repr(e))
        if e.status_code >= 500:
            return jsonify({"error": "El servicio de IA no está disponible ahora mismo. Inténtalo en unos minutos."}), 502
        return jsonify({"error": "Error al comunicarse con el servicio de IA."}), 500

    # Buscamos el primer bloque de texto en vez de dar por hecho que existe
    texto_respuesta = None
    for bloque in mensaje.content:
        if bloque.type == "text":
            texto_respuesta = bloque.text
            break

    if not texto_respuesta:
        print("La respuesta de la IA no contenía texto:", mensaje.content)
        return jsonify({"error": "La IA no devolvió texto. Inténtalo de nuevo."}), 502

    texto_limpio = texto_respuesta.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        datos_json = json.loads(texto_limpio)
    except json.JSONDecodeError:
        print("La IA no devolvió JSON válido:", texto_respuesta)
        return jsonify({"error": "No se pudo interpretar la respuesta de la IA. Inténtalo de nuevo."}), 502

    if not isinstance(datos_json, dict) or not isinstance(datos_json.get("dias"), list):
        print("JSON con formato inesperado:", texto_respuesta)
        return jsonify({"error": "La IA devolvió un formato inesperado. Inténtalo de nuevo."}), 502

    return jsonify(datos_json)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
