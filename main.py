import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Servidor básico para engañar al Port Scanner de Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Iniciar servidor web en un hilo secundario
threading.Thread(target=run_health_check_server, daemon=True).start()

# --- AQUÍ VA EL CÓDIGO PRINCIPAL DE TU BOT ---

import os
import sys
import time
import requests

# Claves obtenidas desde las Variables de Entorno de la nube (Render / Railway)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
API_KEY = os.environ.get("API_KEY")

API_HOST = "tennis-live-data.p.rapidapi.com"
PARTIDOS_NOTIFICADOS = set()


def enviar_alerta_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML",
        "disable_notification": False,  # Fuerza la alerta sonora en el teléfono
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")


def obtener_partidos_en_vivo():
    url = f"https://{API_HOST}/matches-live"
    headers = {"X-RapidAPI-Key": API_KEY, "X-RapidAPI-Host": API_HOST}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            return res.json().get("results", [])
        return []
    except Exception as e:
        print(f"Error consultando la API de tenis: {e}")
        return []


def procesar_partidos():
    partidos = obtener_partidos_en_vivo()
    for partido in partidos:
        match_id = partido.get("id")

        # Evita duplicar alertas de un mismo partido
        if match_id in PARTIDOS_NOTIFICADOS:
            continue

        tournament = partido.get("tournament", {}).get("name", "").upper()
        category = partido.get("category", {}).get("name", "").upper()

        # Condición 1: Solo torneos del circuito WTA
        if "WTA" not in tournament and "WTA" not in category:
            continue

        odds = partido.get("pre_match_odds", {})
        odds_p1 = float(odds.get("player1", 0.0))
        odds_p2 = float(odds.get("player2", 0.0))

        fav_player, odds_fav, player_key = None, 0.0, None

        # Condición 2: Cuota pre-partido de la favorita entre 1.20 y 1.80
        if 1.20 <= odds_p1 <= 1.80:
            fav_player = partido.get("player1", {}).get("name")
            odds_fav = odds_p1
            player_key = "p1"
        elif 1.20 <= odds_p2 <= 1.80:
            fav_player = partido.get("player2", {}).get("name")
            odds_fav = odds_p2
            player_key = "p2"

        if not fav_player:
            continue

        scores = partido.get("scores", {})
        current_set = scores.get("current_set", 1)
        set1_p1 = scores.get("set1_p1")
        set1_p2 = scores.get("set1_p2")

        # Condición 3: Set 1 terminado y la favorita lo perdió
        if current_set < 2 or set1_p1 is None or set1_p2 is None:
            continue

        fav_lost_set1 = False
        if player_key == "p1" and set1_p1 < set1_p2:
            fav_lost_set1 = True
        elif player_key == "p2" and set1_p2 < set1_p1:
            fav_lost_set1 = True

        if not fav_lost_set1:
            continue

        # Condición 4: % de 1er servicio en Set 1 SUPERIOR AL 47% (Actualizado)
        stats = partido.get("stats_set1", {})
        player_stats = stats.get(player_key, {})
        first_serve_pct = float(player_stats.get("first_serve_pct", 0.0))

        if first_serve_pct > 47.0:
            PARTIDOS_NOTIFICADOS.add(match_id)
            rival_name = partido.get(
                "player2" if player_key == "p1" else "player1", {}
            ).get("name")

            mensaje = (
                f"<b>🚨 ALERTA WTA EN VIVO 🚨</b>\n\n"
                f"<b>Torneo:</b> {tournament}\n"
                f"<b>Favorita:</b> {fav_player} (Cuota Pre: <code>{odds_fav:.2f}</code>)\n"
                f"<b>Rival:</b> {rival_name}\n\n"
                f"<b>Set 1:</b> {set1_p1}-{set1_p2} (Perdió la favorita)\n"
                f"<b>1er Servicio Set 1:</b> <code>{first_serve_pct:.1f}%</code> (> 47%)\n\n"
                f"⚠️ <i>Las 3 condiciones se han cumplido.</i>"
            )
            enviar_alerta_telegram(mensaje)


print("🤖 Monitoreo WTA (Servicio > 47%) iniciado...")
enviar_alerta_telegram(
    "✅ ¡Bot de monitoreo WTA actualizado (Servicio > 47%)!"
)

while True:
    procesar_partidos()
    time.sleep(60)
