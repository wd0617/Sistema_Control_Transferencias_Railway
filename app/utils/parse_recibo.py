"""
Parser de recibos de transferencias.
Optimizado para recibos italianos de Western Union, MoneyGram, Ria,
Mondial Bony y Monty. Extrae solo lo esencial: nombre, apellido,
documento, teléfono, monto (EUR), fecha de nacimiento y servicio.
"""

import re


def parsear_recibo(texto):
    """
    Recibe texto crudo de un recibo y devuelve dict con datos extraídos.
    """
    if not texto:
        return {}

    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    resultado = {}

    # --- NOMBRE ---
    nombre, apellido = _extraer_nombre(lineas)
    if nombre:
        resultado['nombre'] = nombre
        resultado['apellido'] = apellido or ''

    # --- DOCUMENTO ---
    doc = _extraer_documento(lineas)
    if doc:
        resultado['documento'] = doc

    # --- TELEFONO ---
    tel = _extraer_telefono(lineas)
    if tel:
        resultado['telefono'] = tel

    # --- MONTO ---
    monto = _extraer_monto(lineas)
    if monto:
        resultado['monto'] = round(monto, 2)

    # --- FECHA DE NACIMIENTO ---
    fecha = _extraer_fecha_nacimiento(lineas)
    if fecha:
        resultado['fecha_nacimiento_raw'] = fecha

    # --- SERVICIO ---
    resultado['servicio_hint'] = _detectar_servicio(texto)

    return resultado


def _extraer_nombre(lineas):
    """Busca nombre y apellido en el recibo."""
    # Estrategia 1: Nome + Cognome separados (Mondial Bony, etc.)
    nome = None
    cognome = None
    for linea in lineas:
        lu = linea.upper()
        if lu.startswith('NOME:') or lu.startswith('NOME '):
            val = linea.split(':', 1)[-1].strip()
            if val and len(val) > 1:
                nome = val
        elif lu.startswith('COGNOME:') or lu.startswith('COGNOME '):
            val = linea.split(':', 1)[-1].strip()
            if val and len(val) > 1:
                cognome = val
    if nome and cognome:
        return nome, cognome

    # Estrategia 2: Nome e cognome del cliente (Ria)
    for linea in lineas:
        lu = linea.upper()
        if 'NOME E COGNOME DEL CLIENTE' in lu or 'NOME E COGNOME' in lu:
            val = linea.split(':', 1)[-1].strip()
            if val:
                return _split_nombre(val)

    # Estrategia 3: Mittente: (WU, Monty)
    for linea in lineas:
        lu = linea.upper()
        if lu.startswith('MITTENTE:') or lu.startswith('MITTENTE '):
            val = linea.split(':', 1)[-1].strip()
            if val:
                return _split_nombre(val)

    # Estrategia 4: Informazioni Mittente (MoneyGram) - valor en siguiente línea
    for i, linea in enumerate(lineas):
        if 'INFORMAZIONI MITTENTE' in linea.upper():
            for j in range(i + 1, min(i + 5, len(lineas))):
                candidato = lineas[j]
                # Debe ser una línea que parezca nombre (2-4 palabras alfabéticas)
                palabras = candidato.split()
                if 2 <= len(palabras) <= 4:
                    alfa = [p for p in palabras if p.isalpha() and len(p) > 1]
                    if len(alfa) >= 2:
                        return _split_nombre(candidato)
            break

    # Estrategia 5: Ordinante (Monty) puede tener nombre entre paréntesis o después de dos puntos
    for linea in lineas:
        lu = linea.upper()
        if 'ORDINANTE' in lu and ('TEL.' in lu or 'TEL:' in lu):
            # Formato: "Ordinante (Tel.): NOMBRE APELLIDO (telefono)"
            # o "Ordinante (Tel.): APELLIDO, NOMBRE (telefono)"
            val = linea.split(':', 1)[-1].strip()
            # Quitar teléfono entre paréntesis al final
            val = re.sub(r'\s*\(\+?\d[\d\s-]+\)\s*$', '', val)
            val = val.strip()
            if val:
                return _split_nombre(val)

    return None, None


def _split_nombre(texto):
    """Separa nombre completo en (nombre, apellido)."""
    texto = texto.strip().strip(':').strip()
    if not texto:
        return None, None

    # Formato "Apellido, Nombre"
    if ',' in texto:
        partes = [p.strip() for p in texto.split(',')]
        if len(partes) == 2:
            return partes[1], partes[0]

    palabras = texto.split()
    palabras = [p for p in palabras if p.isalpha() or (p.isalpha() and len(p) > 1)]
    # Filtrar palabras no alfabéticas pero conservar apellidos con guion?
    palabras = [p for p in texto.split() if re.match(r'^[A-ZÀ-ÿ-]+$', p, re.I) and len(p) > 1]

    if len(palabras) < 2:
        return None, None

    if len(palabras) == 2:
        return palabras[0], palabras[1]
    elif len(palabras) == 3:
        return palabras[0], ' '.join(palabras[1:])
    else:
        return ' '.join(palabras[:2]), ' '.join(palabras[2:])


def _extraer_documento(lineas):
    """Extrae número de documento del remitente."""
    keywords = [
        'NUMERO DEL DOCUMENTO:', 'NUMERO DOC.:', 'NUMERO DOCUMENTO:',
        'DOCUMENTO:', 'N. DOCUMENTO:', 'N.DOCUMENTO:', 'NUMERO DOC:',
        'NUMERO DOCUMENTO', 'NUMERO ID:', 'NUMERO ID'
    ]
    for linea in lineas:
        lu = linea.upper()
        for kw in keywords:
            if kw in lu:
                val = linea.split(':', 1)[-1].strip()
                if val and len(val) >= 5:
                    # Si es "Passaporto 122073848", quedarse solo con el número
                    partes = val.split()
                    if len(partes) == 2 and len(partes[1]) >= 5:
                        tipos = ['PASSAPORTO', 'CARTA', 'IDENTITA', 'IDENTITÀ', 'NIE', 'DNI']
                        if any(t in partes[0].upper() for t in tipos):
                            return partes[1]
                    return val
    return None


def _extraer_telefono(lineas):
    """Extrae teléfono del remitente. Ignora números de agencia."""
    keywords = ['TELEFONO:', 'TEL.:', 'TEL:']
    for linea in lineas:
        lu = linea.upper()
        for kw in keywords:
            if kw in lu:
                val = linea.split(':', 1)[-1].strip()
                if val:
                    limpio = re.sub(r'[^\d+]', '', val)
                    # Filtrar: teléfonos personales suelen tener 9-15 dígitos
                    # Los de agencia pueden ser más cortos o tener prefijos raros
                    if 9 <= len(limpio) <= 15:
                        return limpio
    return None


def _extraer_monto(lineas):
    """
    Extrae el monto pagado en EUR.
    Ignora montos en moneda destino (XOF, DOP, etc.).
    """
    # Keywords que indican el monto CORRECTO (lo que pagó el cliente en EUR)
    keywords_validos = [
        'TOTALE:', 'TOTALE CONTANTE', 'IMPORTO TOTALE PAGATO:',
        'IMPORTO INVIATO:', 'IMPORTO DI TRASFERIMENTO:',
        'MONTO:', 'TOTAL:', 'IMPORTO CONTANTE'
    ]
    # Keywords que indican montos a IGNORAR (moneda destino, comisiones, etc.)
    keywords_ignorar = [
        'IMPORTO DA RICEVERE', 'IMPORTO IN VALUTA LOCALE',
        'INVIATO IN VALUTA', 'TOTALE AL DESTINATARIO',
        'TASSE DI', 'COMMISSIONE', 'TASSO DI', 'TASSO DI CAMBIO',
        'SPREAD', 'ALTRE SPESE', 'IMPOSTA'
    ]

    for linea in lineas:
        lu = linea.upper()

        # Ignorar si contiene keyword de ignorar
        if any(ig.upper() in lu for ig in keywords_ignorar):
            continue

        # Si contiene keyword válido y EUR/€/EURO
        if any(kw.upper() in lu for kw in keywords_validos):
            m = re.search(r'(?:EUR|EURO|€)\s*([\d\.,]+)|([\d\.,]+)\s*(?:EUR|EURO|€)', linea, re.IGNORECASE)
            if m:
                val = m.group(1) or m.group(2)
                parsed = _parse_monto(val)
                if parsed and parsed > 0:
                    return parsed

    # Fallback: buscar cualquier línea con EUR/€ que NO tenga keywords de ignorar
    for linea in lineas:
        lu = linea.upper()
        if any(ig.upper() in lu for ig in keywords_ignorar):
            continue
        if 'EUR' in lu or 'EURO' in lu or '€' in linea:
            m = re.search(r'(?:EUR|EURO|€)\s*([\d\.,]+)|([\d\.,]+)\s*(?:EUR|EURO|€)', linea, re.IGNORECASE)
            if m:
                val = m.group(1) or m.group(2)
                parsed = _parse_monto(val)
                if parsed and parsed > 0 and parsed < 50000:
                    return parsed

    return None


def _parse_monto(raw_str):
    """
    Convierte un string de monto europeo a float.
    500.00 -> 500.0, 1.250,00 -> 1250.0, 999,00 -> 999.0
    """
    if not raw_str:
        return None
    s = raw_str.strip()
    has_dot = '.' in s
    has_comma = ',' in s

    if has_dot and has_comma:
        last_dot = s.rfind('.')
        last_comma = s.rfind(',')
        if last_comma > last_dot:
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif has_comma:
        parts = s.split(',')
        if len(parts) == 2 and len(parts[-1]) <= 2:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    elif has_dot:
        parts = s.split('.')
        if len(parts) == 2 and len(parts[-1]) <= 2:
            pass  # ya está bien
        else:
            s = s.replace('.', '')

    try:
        val = float(s)
        if 0 < val < 50000:
            return val
        return None
    except ValueError:
        return None


def _extraer_fecha_nacimiento(lineas):
    """Extrae fecha de nacimiento del remitente."""
    keywords = [
        'DATA NASCITA:', 'DATA DI NASCITA:', 'DATA DI NASCITA',
        'DATA NASCITA'
    ]
    for linea in lineas:
        lu = linea.upper()
        for kw in keywords:
            if kw in lu:
                val = linea.split(':', 1)[-1].strip()
                if val:
                    return val
    return None


def _detectar_servicio(texto):
    """Detecta el servicio de transferencia a partir del texto."""
    tu = texto.upper()
    if 'RIA ' in tu or 'RIA\n' in tu or 'RIAMONEY' in tu:
        return 'Ria Money Transfer'
    if 'WESTERN UNION' in tu or 'WU ' in tu:
        return 'Western Union'
    if 'MONEYGRAM' in tu:
        return 'MoneyGram'
    if 'MONDIAL' in tu or 'MONDIAL BONY' in tu:
        return 'Mondial Bony'
    if 'MONTY' in tu or 'MONTY GLOBAL' in tu:
        return 'Monty'
    return None
