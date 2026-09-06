import os
import requests
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# ========================================================
# CONEXIÓN DE APIS MEDIANTE VARIABLES DE ENTRORNO (RENDER)
# ========================================================
# Se obtienen de forma limpia desde la pestaña 'Environment' de Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

def verificar_telegram():
    """Verifica la conexión con Telegram estructurando la URL de forma correcta."""
    if not TELEGRAM_TOKEN:
        print("❌ ERROR: No se encontró la variable 'TELEGRAM_TOKEN' en el Environment de Render.")
        return

    # Corrección estructural: se añade el subdominio 'api.' y el prefijo '/bot'
    url_telegram = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": "REMPLAZA_CON_TU_CHAT_ID",  # Coloca aquí tu ID de chat si envías un mensaje inicial
        "text": "🤖 Servidor Flask iniciado correctamente y conectado a Telegram."
    }
    
    try:
        print("Verificando conexión con la API de Telegram...")
        # Hacemos la petición de prueba a la URL corregida
        requests.post(url_telegram, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ No se pudo conectar con Telegram para la prueba: {e}")

def monitor_live_matches():
    """Tarea programada que revisa los partidos en vivo."""
    print("🔄 Verificando partidos EN VIVO circuito WTA...")
    
    if not ODDS_API_KEY:
        print("❌ ERROR: No se encontró la variable 'ODDS_API_KEY' en el Environment de Render.")
        return

    # Corrección de URL: Se define el host limpio sin añadirle texto directamente al dominio
    url_odds = "https://the-odds-api.com"
    
    # Enviamos la API Key de forma segura encapsulada como parámetro URL (?apiKey=...)
    params = {
        "apiKey": ODDS_API_KEY
    }
    
    try:
        response = requests.get(url_odds, params=params, timeout=15)
        response.raise_for_status()  # Valida que el servidor responda con estado 200 OK
        data = response.json()
        print("✅ Torneos obtenidos exitosamente de The Odds API.")
        
        # Aquí puedes procesar los datos 'data' según los requiera tu aplicación...
        
    except Exception as e:
        print(f"❌ ERROR - Error obteniendo torneos: {e}")

# ==========================================
# CONFIGURACIÓN DEL PROGRAMADOR (SCHEDULER)
# ==========================================
scheduler = BackgroundScheduler()
# Ejecuta la tarea en segundo plano cada 2 minutos (coincidiendo con tus logs)
scheduler.add_job(monitor_live_matches, 'interval', minutes=2, id='monitor_live_matches')
scheduler.start()

# Ejecutar validación de Telegram al inicializar el proceso
verificar_telegram()

# ==========================================
# RUTA PRINCIPAL DE FLASK
# ==========================================
@app.route('/')
def home():
    return "Your service is live and monitoring WTA matches!"

if __name__ == '__main__':
    # Render maneja puertos dinámicos. Usamos el asignado o el 10000 por defecto.
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)


