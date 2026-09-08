"""
Utilidades para generación de enlaces y mensajes de WhatsApp para clientes.
Soporte multilingüe con énfasis en Italiano (mercado italiano de remesas) y Español.
"""

import re
import urllib.parse


def formatear_telefono_whatsapp(telefono):
    """
    Normaliza el número de teléfono para enlaces wa.me.
    - Remueve caracteres no numéricos.
    - Si tiene prefijo 00, lo quita.
    - Si es un móvil italiano típico (10 dígitos empezando con 3), añade el prefijo 39.
    - Si es un móvil español típico (9 dígitos empezando con 6 o 7), añade el prefijo 34.
    """
    if not telefono:
        return ''

    # Solo dígitos
    digitos = re.sub(r'\D', '', str(telefono))
    if not digitos:
        return ''

    # Si empieza por 00, removerlo (ej. 0039... -> 39...)
    if digitos.startswith('00'):
        digitos = digitos[2:]

    # Si tiene 10 dígitos y empieza por 3 (móvil italiano: 3xx xxx xxxx), anteponer 39
    if len(digitos) == 10 and digitos.startswith('3'):
        digitos = '39' + digitos
    # Si tiene 9 dígitos y empieza por 6 o 7 (móvil español), anteponer 34
    elif len(digitos) == 9 and digitos[0] in ('6', '7'):
        digitos = '34' + digitos

    return digitos


def generar_mensaje_whatsapp(transaccion, idioma='it'):
    """
    Genera el texto amigable y formateado del comprobante para el cliente.
    Idiomas soportados: 'it' (Italiano, por defecto) y 'es' (Español).
    """
    cliente_nombre = 'Cliente'
    if transaccion.cliente:
        cliente_nombre = transaccion.cliente.nombre.strip().title()

    servicio_nombre = transaccion.servicio.nombre if transaccion.servicio else 'Transferencia'
    monto_str = f"{transaccion.monto:.2f}"
    comision_val = transaccion.comision or 0.0
    comision_str = f"{comision_val:.2f}"
    total_str = f"{(transaccion.monto + comision_val):.2f}"
    fecha_str = transaccion.fecha.strftime('%d/%m/%Y %H:%M') if transaccion.fecha else ''
    referencia_str = transaccion.referencia.strip() if transaccion.referencia else None

    if idioma == 'es':
        ref_line = f"🔢 Código / Referencia: {referencia_str}\n" if referencia_str else ""
        return (
            f"¡Hola {cliente_nombre}! 👋\n"
            f"Gracias por elegir nuestra agencia.\n\n"
            f"Te confirmamos los datos de tu envío:\n"
            f"📌 Servicio: {servicio_nombre}\n"
            f"💰 Monto enviado: {monto_str} €\n"
            f"🧾 Comisión: {comision_str} €\n"
            f"💳 Total pagado: {total_str} €\n"
            f"{ref_line}"
            f"📅 Fecha: {fecha_str}\n\n"
            f"¡Muchas gracias por tu confianza y hasta pronto! ✨"
        )

    # Italiano (por defecto)
    ref_line = f"🔢 Codice / MTCN: {referencia_str}\n" if referencia_str else ""
    return (
        f"Ciao {cliente_nombre}! 👋\n"
        f"Grazie per aver scelto la nostra agenzia.\n\n"
        f"Ti confermiamo i dettagli del tuo invio:\n"
        f"📌 Servizio: {servicio_nombre}\n"
        f"💰 Importo inviato: {monto_str} €\n"
        f"🧾 Commissione: {comision_str} €\n"
        f"💳 Totale pagato: {total_str} €\n"
        f"{ref_line}"
        f"📅 Data: {fecha_str}\n\n"
        f"Grazie per la tua fiducia e a presto! ✨"
    )


def generar_url_whatsapp(transaccion, idioma='it'):
    """
    Genera el enlace directo para enviar el mensaje por WhatsApp.
    Si el cliente tiene teléfono, genera 'https://wa.me/{telefono}?text=...'.
    Si no tiene teléfono, genera 'https://api.whatsapp.com/send?text=...'
    para que el cajero seleccione el chat en WhatsApp.
    """
    telefono = ''
    if transaccion.cliente and transaccion.cliente.telefono:
        telefono = formatear_telefono_whatsapp(transaccion.cliente.telefono)

    mensaje = generar_mensaje_whatsapp(transaccion, idioma=idioma)
    encoded_text = urllib.parse.quote(mensaje)

    if telefono:
        return f"https://wa.me/{telefono}?text={encoded_text}"
    return f"https://api.whatsapp.com/send?text={encoded_text}"
