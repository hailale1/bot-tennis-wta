import os
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# 1. Servidor de salud para mantener Render activo gratis
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot WTA en vivo activo")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_health_check_server, daemon=True).start()

# 2. Configuración de Credenciales
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TENNIS_API_KEY = os.environ.get("TENNIS_API_KEY")

API_URL = "https://api.tennis-data.p.rapidapi.com" # Ajustar a tu endpoint de API
HEADERS = {
    "x-rapidapi-key": TENNIS_API_KEY,
    "x-rapidapi-host": "tennis-data.p.rapidapi.com"
}

PARTIDOS_NOTIFICADOS = set()

def enviar_alerta_telegram(mensaje):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Faltan credenciales de Telegram.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")

def parse_val(raw_val, default="N/D"):
    """Limpia y da formato a porcentajes o valores numéricos de la API"""
    if raw_val is None or raw_val == "":
        return default
    val_str = str(raw_val).strip()
    return val_str

def parse_service_pct(raw_val):
    """Convierte cualquier formato de % de servicio a float para la condición"""
    if raw_val is None:
        return 0.0
    try:
        val_str = str(raw_val).replace("%", "").strip()
        val_float = float(val_str)
        if 0 < val_float <= 1.0:
            val_float = val_float * 100.0
        return val_float
    except Exception:
        return 0.0

def extraer_bloque_stats(player_stats, nombre_jugadora):
    """Extrae las 7 métricas solicitadas para una jugadora"""
    srv_1st_pct = parse_val(player_stats.get("first_serve_pct") or player_stats.get("1st_serve_pct"))
    srv_1st_won = parse_val(player_stats.get("first_serve_points_won") or player_stats.get("1st_serve_won"))
    srv_2nd_won = parse_val(player_stats.get("second_serve_points_won") or player_stats.get("2nd_serve_won"))
    unforced_err = parse_val(player_stats.get("unforced_errors") or player_stats.get("ue"))
    bp_saved    = parse_val(player_stats.get("break_points_saved") or player_stats.get("bp_saved"))
    bp_won      = parse_val(player_stats.get("break_points_converted") or player_stats.get("bp_won"))
    games_won   = parse_val(player_stats.get("total_games_won") or player_stats.get("games_won"))

    return (
        f"👤 <b>{nombre_jugadora}</b>\n"
        f"• % 1er Servicio: <code>{srv_1st_pct}</code>\n"
        f"• % Puntos 1er Servicio Ganados: <code>{srv_1st_won}</code>\n"
        f"• % Puntos 2do Servicio Ganados: <code>{srv_2nd_won}</code>\n"
        f"• Errores No Forzados: <code>{unforced_err}</code>\n"
        f"• Pts de Quiebre Salvados: <code>{bp_saved}</code>\n"
        f"• Pts de Quiebre Ganados: <code>{bp_won}</code>\n"
        f"• Total Juegos Ganados: <code>{games_won}</code>\n"
    )

def monitorear_wta():
    enviar_alerta_telegram("🤖 <b>Bot WTA de monitoreo (Estadísticas Completas) activo.</b>")
    print("Monitoreo WTA iniciado...")
    
    while True:
        try:
            res = requests.get(f"{API_URL}/live", headers=HEADERS, timeout=15)
            if res.status_code != 200:
                time.sleep(60)
                continue
                
            data = res.json()
            matches = data.get("response", []) or data.get("matches", [])

            for partido in matches:
                match_id = partido.get("id") or partido.get("match_id")
                if not match_id or match_id in PARTIDOS_NOTIFICADOS:
                    continue

                tournament = partido.get("tournament", {}).get("name", "Torneo WTA")
                p1 = partido.get("player1", {}).get("name", "Jugadora 1")
                p2 = partido.get("player2", {}).get("name", "Jugadora 2")

                set1_p1 = partido.get("scores", {}).get("set1_p1", 0)
                set1_p2 = partido.get("scores", {}).get("set1_p2", 0)
                set1_finished = partido.get("scores", {}).get("set1_finished", False) or (set1_p1 >= 6 or set1_p2 >= 6)

                if not set1_finished:
                    continue

                fav_player = None
                rival_name = None
                player_key = None
                
                odds_fav = float(partido.get("odds_pre", 1.50))
                
                if 1.20 <= odds_fav <= 1.80:
                    if set1_p1 < set1_p2:
                        fav_player = p1
                        rival_name = p2
                        player_key = "player1"
                    elif set1_p2 < set1_p1:
                        fav_player = p2
                        rival_name = p1
                        player_key = "player2"

                if not fav_player:
                    continue

                stats = partido.get("stats", {}) or partido.get("statistics", {})
                p1_stats = stats.get("player1", {})
                p2_stats = stats.get("player2", {})
                
                fav_stats = p1_stats if player_key == "player1" else p2_stats
                raw_pct = fav_stats.get("first_serve_pct") or fav_stats.get("first_serve_percentage") or fav_stats.get("1st_serve_pct")
                first_serve_pct = parse_service_pct(raw_pct)

                # Condición: Primer servicio > 47% (o 0.0 si la API aún no desglosa el % específico)
                if first_serve_pct > 47.0 or first_serve_pct == 0.0:
                    
                    # Generar bloques detallados de ambas jugadoras
                    stats_p1_text = extraer_bloque_stats(p1_stats, p1)
                    stats_p2_text = extraer_bloque_stats(p2_stats, p2)

                    mensaje = (
                        f"🚨 <b>ALERTA TENIS WTA EN VIVO</b> 🚨\n\n"
                        f"🏆 <b>Torneo:</b> {tournament}\n"
                        f"📉 <b>Resultado Set 1:</b> {p1} {set1_p1} - {set1_p2} {p2}\n"
                        f"⭐ <b>Favorita Pre-Partido:</b> {fav_player} (Cuota: {odds_fav:.2f})\n\n"
                        f"📊 <b>ESTADÍSTICAS DEL PARTIDO (SET 1)</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"{stats_p1_text}\n"
                        f"{stats_p2_text}\n"
                        f"⚠️ <i>Las condiciones de racha e indicadores se han cumplido.</i>"
                    )
                    enviar_alerta_telegram(mensaje)
                    PARTIDOS_NOTIFICADOS.add(match_id)

        except Exception as e:
            print(f"Error en el ciclo principal: {e}")

        time.sleep(60)

if __name__ == "__main__":
    monitorear_wta()
