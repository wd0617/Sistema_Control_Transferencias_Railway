"""Notificaciones al dueño de la plataforma vía Telegram (Bot API).

Configuración (variables de entorno):
- TELEGRAM_BOT_TOKEN: token del bot creado con @BotFather
- TELEGRAM_CHAT_ID: id del chat donde llegan los avisos (hablar primero
  al bot y consultar https://api.telegram.org/bot<token>/getUpdates)

Si falta alguna de las dos, las notificaciones se omiten silenciosamente.
Nunca lanza excepciones: un fallo de Telegram no debe romper un request.
"""
import json
import os
import urllib.request
import urllib.error

from flask import current_app


def notificar_telegram(texto):
    """Envía un mensaje de Telegram al chat configurado. Devuelve True si se envió."""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return False

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = json.dumps({
        'chat_id': chat_id,
        'text': texto,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True,
    }).encode('utf-8')

    try:
        req = urllib.request.Request(url, data=payload,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, ValueError) as e:
        try:
            current_app.logger.warning(f'No se pudo enviar notificación Telegram: {e}')
        except RuntimeError:
            pass  # Sin contexto de app
        return False
