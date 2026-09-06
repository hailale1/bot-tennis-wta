import os
import requests
import threading
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
            f"🏆 **Torneo:** WTA US OPEN (PRUEBA ARRANCADO)\n"
            f"🎾 **Partido:** Iga Swiatek vs Aryna Sabalenka\n"
            f"⭐ **Favorita:** Iga Swiatek\n\n"
            f"🎯 **Probabilidad de Remontada:** `72.5%`"
        )
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": message, 
            "parse_mode": "Markdown"
        }
        
        try:
            r = requests.post(url, json=payload, timeout=10)
            print(f"Respuesta de Telegram en arranque: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"Error de red en arranque: {e}")

@app.route('/')
def home():
    # Disparar también si entran a la página principal por si acaso
    send_telegram_alert()
    return "Servidor WTA Activo y Alerta Enviada", 200

def run_auto_start():
    # Ejecuta el envío inmediatamente al encender el servidor
    send_telegram_alert()

if __name__ == "__main__":
    # Arranca el hilo de disparo automático antes de levantar la web
    threading.Thread(target=run_auto_start, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
