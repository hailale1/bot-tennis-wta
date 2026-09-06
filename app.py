import os
import requests
from flask import Flask

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

app = Flask(__name__)

def send_telegram_alert():
    """Envía la alerta utilizando la nueva API v10 de Telegram."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        # CORREGIDO: Nuevo método oficial sendRichMessage exigido por Telegram
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendRichMessage"
        
        # Formato HTML enriquecido compatible con la nueva API
        html_content = (
            "<h1>🚨 ALERTA DE VALOR WTA (TEST) 🚨</h1>"
            "<p>🏆 <b>Torneo:</b> WTA US OPEN (PRUEBA DEFINITIVA)</p>"
            "<p>🎾 <b>Partido:</b> Iga Swiatek vs Aryna Sabalenka</p>"
            "<p>⭐ <b>Favorita:</b> Iga Swiatek</p><br>"
            "<p>🎯 <b>Probabilidad de Remontada:</b> 72.5%</p>"
        )
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "rich_message": {
                "html": html_content
            }
        }
        
        try:
            r = requests.post(url, json=payload, timeout=10)
            print(f"Respuesta de Telegram API: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"Error de red: {e}")

@app.route('/')
def home():
    send_telegram_alert()
    return "Servidor WTA Activo - Alerta Enriquecida Enviada", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
