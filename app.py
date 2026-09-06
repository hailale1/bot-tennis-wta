import os
import requests
from flask import Flask

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

app = Flask(__name__)

def send_telegram_alert():
    """Envía una segunda alerta simulando un caso real con el diseño definitivo."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendRichMessage"
        
        # Formato de diseño real con emojis y estructura limpia
        html_content = (
            "<b>🚨 ALERTA DE VALOR WTA 🚨</b><br><br>"
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
            print(f"Segunda prueba enviada: {r.status_code}")
        except Exception as e:
            print(f"Error de red: {e}")

@app.route('/')
def home():
    send_telegram_alert()
    return "Segunda Alerta Enviada con Diseño Real", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
