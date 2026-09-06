import os
import requests
import threading
from flask import Flask

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

app = Flask(__name__)

def send_telegram_alert():
    """Envía la alerta en texto plano directo para evitar bloqueos de formato."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        # Texto plano sin asteriscos ni comillas que puedan romper el formato
        message = (
            "ALERTA DE VALOR WTA (TEST)\n\n"
            "Torneo: WTA US OPEN (PRUEBA FINAL)\n"
            "Partido: Iga Swiatek vs Aryna Sabalenka\n"
            "Favorita: Iga Swiatek\n\n"
            "Probabilidad de Remontada: 72.5%"
        )
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": message
        }
        
        try:
            r = requests.post(url, json=payload, timeout=10)
            print(f"Respuesta de Telegram: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"Error de red: {e}")

@app.route('/')
def home():
    send_telegram_alert()
    return "Servidor WTA Activo y Alerta de Texto Plano Enviada", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

