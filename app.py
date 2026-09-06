import os
import requests
import threading
from flask import Flask

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

app = Flask(__name__)

def send_telegram_alert():
    """Envía la alerta detallada de tenis usando el método sendRichMessage."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendRichMessage"
        
        html_content = (
            "<b>🚨 ALERTA DE VALOR WTA (TEST) 🚨</b><br><br>"
            "🏆 <b>Torneo:</b> WTA 1000 MADRID Open<br>"
            "🎾 <b>Partido:</b> Paula Badosa vs Coco Gauff<br>"
            "⭐ <b>Favorita en Apuros:</b> Paula Badosa<br><br>"
            "📊 <b>Comparativa de Cuotas:</b><br>"
            "• Cuota Pre-Partido: <code>1.45</code><br>"
            "• Cuota en Vivo Actual: <code>2.62</code> <i>(¡Favorita perdiendo 1er Set!)</i><br><br>"
            "🎯 <b>Probabilidad de Remontada:</b> <b>78.4%</b>"
        )
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "rich_message": {
                "html": html_content
            }
        }
        
        try:
            r = requests.post(url, json=payload, timeout=10)
            print(f"Resultado del envío automático: {r.status_code}")
        except Exception as e:
            print(f"Error de red: {e}")

@app.route('/')
def home():
    return "Bot WTA Activo y Monitoreando", 200

def run_auto_start():
    # Dispara la alerta inmediatamente al encender el servidor sin requerir links
    send_telegram_alert()

if __name__ == "__main__":
    # Arranca el hilo de envío antes de que cargue la web
    threading.Thread(target=run_auto_start, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

