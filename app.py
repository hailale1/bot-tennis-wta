import os
import requests
from flask import Flask

# Leer las variables guardadas en el panel de Render
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

app = Flask(__name__)

def send_telegram_alert():
    """Función de envío original corregida utilizando formato JSON estricto."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        message = (
            f"🚨 **ALERTA DE VALOR WTA (TEST)** 🚨\n\n"
            f"🏆 **Torneo:** WTA US OPEN (PRUEBA)\n"
            f"🎾 **Partido:** Iga Swiatek vs Aryna Sabalenka\n"
            f"⭐ **Favorita:** Iga Swiatek\n\n"
            f"🎯 **Probabilidad de Remontada:** `72.5%`"
        )
        
        # CORRECCIÓN DEFINITIVA: Usar formato JSON para que Telegram acepte el Markdown y los emojis
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": message, 
            "parse_mode": "Markdown"
        }
        
        try:
            # Se cambia 'data=payload' por 'json=payload' para asegurar la recepción
            r = requests.post(url, json=payload, timeout=10)
            print(f"Respuesta de Telegram: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"Error de red: {e}")

@app.route('/')
def home():
    return "Servidor WTA Activo", 200

@app.route('/test-alert')
def test_alert():
    send_telegram_alert()
    return "Alerta de prueba disparada. Revisa tu Telegram.", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
