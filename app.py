import os
import requests
import threading
from flask import Flask

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

app = Flask(__name__)

def send_telegram_alert():
    """Envía la alerta utilizando formato MarkdownV2 limpio para evitar bloqueos de la API."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendRichMessage"
        
        # Formato Markdown puro y limpio exigido por la API de Telegram v10
        markdown_content = (
            "🚨 *ALERTA DE VALOR WTA (TEST)* 🚨\n\n"
            "🏆 *Torneo:* WTA 1000 MADRID Open\n"
            "🎾 *Partido:* Paula Badosa vs Coco Gauff\n"
            "⭐ *Favorita en Apuros:* Paula Badosa\n\n"
            "📊 *Comparativa de Cuotas:*\n"
            "• Cuota Pre-Partido: `1.45`\n"
            "• Cuota en Vivo Actual: `2.62` _(Favorita perdiendo)_ \n\n"
            "🎯 *Probabilidad de Remontada:* *78.4%*"
        )
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "rich_message": {
                "markdown": markdown_content
            }
        }
        
        try:
            r = requests.post(url, json=payload, timeout=10)
            print(f"Resultado del envío Markdown: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"Error de red: {e}")

@app.route('/')
def home():
    return "Bot WTA Activo", 200

def run_auto_start():
    # Envía el mensaje inmediatamente al arrancar el servidor
    send_telegram_alert()

if __name__ == "__main__":
    threading.Thread(target=run_auto_start, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

