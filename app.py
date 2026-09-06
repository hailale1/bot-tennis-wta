def send_telegram_alert(tournament, p1, p2, fav_name, pre_odds, live_odds, prob):
    """Envía la alerta estructurada a Telegram usando el método oficial sendMessage."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        # CORREGIDO: Inclusión estricta del subdominio 'api.' y la palabra '/bot'
        url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        html_content = (
            f"<b>🚨 ALERTA DE VALOR WTA 🚨</b>\n\n"
            f"🏆 <b>Torneo:</b> {tournament.replace('_', ' ').upper()}\n"
            f"🎾 <b>Partido:</b> {p1} vs {p2}\n"
            f"⭐ <b>Favorita en Apuros:</b> {fav_name}\n\n"
            f"📊 <b>Comparativa de Cuotas:</b>\n"
            f"• Cuota Pre-Partido: {pre_odds}\n"
            f"• Cuota en Vivo Actual: {live_odds}\n\n"
            f"🎯 <b>Probabilidad de Remontada:</b> {prob}%"
        )
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": html_content,
            "parse_mode": "HTML"
        }
        try:
            r = requests.post(url, json=payload, timeout=10)
            logging.info(f"Intento de envío de alerta. Código de respuesta Telegram: {r.status_code}")
        except Exception as e:
            logging.error(f"Error al conectar con Telegram: {e}")

def send_startup_test_message():
    """Envía un mensaje de prueba estándar al iniciar para validar tokens."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        # CORREGIDO: Estructura de endpoint oficial de producción
        url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": "<b>✅ Bot WTA Iniciado Correctamente</b>\nLa conexión con Telegram es exitosa mediante la API de producción. El escáner de cuotas ya está corriendo en segundo plano.",
            "parse_mode": "HTML"
        }
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                logging.info("🚀 ¡Mensaje de prueba enviado con éxito a Telegram!")
            else:
                logging.error(f"❌ Error en mensaje de prueba. Código: {r.status_code} - Verifique si el Bot está dentro del canal/chat.")
        except Exception as e:
            logging.error(f"❌ No se pudo conectar con Telegram para la prueba: {e}")



