from flask import Flask, request, jsonify
from flask_cors import CORS
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

@app.route("/menu", methods=["POST"])
def generar_menu():
    datos = request.get_json()
    ingredientes = datos.get("ingredientes", "")
    fecha_inicio = datos.get("fechaInicio", "")

    prompt = f"""Tengo estos ingredientes en la nevera: {ingredientes}.
Generame un menu para 7 dias empezando el {fecha_inicio} (formato YYYY-MM-DD, dias consecutivos).
Usa principalmente esos ingredientes.
Responde SOLO con JSON valido, sin texto antes ni despues, con este formato exacto:
{{"dias": [{{"fecha": "YYYY-MM-DD", "Desayuno": "texto corto", "Almuerzo": "texto corto", "Merienda": "texto corto", "Cena": "texto corto"}}]}}
"""

    mensaje = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system="Eres una asistente que genera menús semanales saludables usando principalmente los ingredientes que el usuario tiene en la nevera. Responde siempre en JSON válido, sin texto adicional.",
        messages=[{"role": "user", "content": prompt}]
    )

    texto_respuesta = mensaje.content[0].text
    texto_limpio = texto_respuesta.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        datos_json = json.loads(texto_limpio)
    except json.JSONDecodeError:
        return jsonify({"error": "No se pudo interpretar la respuesta", "raw": texto_respuesta}), 500

    return jsonify(datos_json)

if __name__ == "__main__":
    app.run(port=5000, debug=True)