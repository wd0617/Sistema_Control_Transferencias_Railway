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

    # --- REFERENCIA / MTCN ---
    ref = _extraer_referencia(lineas, texto)
    if ref:
        resultado['referencia'] = ref

    return resultado


def _extraer_nombre(lineas):
    """Busca nombre y apellido del remitente en el recibo (evitando el beneficiario)."""
    # 1. Estrategia Nome + Cognome explícitos (Mondial Bony, tablas)
    nome = None
    cognome = None
    en_beneficiario = False

    for i, linea in enumerate(lineas):
        lu = linea.upper().strip()
        if any(b in lu for b in ['DATI DEL BENEFICIARIO', 'BENEFICIARIO', 'DESTINATARIO', 'RECEIVER']):
            en_beneficiario = True
        if any(m in lu for m in ['DATI DEL MITTENTE', 'MITTENTE', 'SENDER', 'ORDINANTE', 'DATI CLIENTE']):
            en_beneficiario = False

        if en_beneficiario:
            continue

        if lu.startswith('NOME:') or lu.startswith('NOME '):
            val = linea.split(':', 1)[-1].strip()
            if val and len(val) > 1 and val.upper() != 'NOME':
                nome = val
        elif lu == 'NOME' and i + 1 < len(lineas):
            cand = lineas[i + 1].strip()
            if cand and ':' not in cand and len(cand) > 1:
                nome = cand

        elif lu.startswith('COGNOME:') or lu.startswith('COGNOME '):
            val = linea.split(':', 1)[-1].strip()
            if val and len(val) > 1 and val.upper() != 'COGNOME':
                cognome = val
        elif lu == 'COGNOME' and i + 1 < len(lineas):
            cand = lineas[i + 1].strip()
            if cand and ':' not in cand and len(cand) > 1:
                cognome = cand

    if nome and cognome:
        return nome, cognome

    # 2. Estrategia: Palabras clave de remitente / cliente
    keywords_remitente = [
        'NOME E COGNOME DEL CLIENTE', 'NOME E COGNOME DEL MITTENTE',
        'NOME E COGNOME', 'NOME COMPLETO', 'DATI DEL MITTENTE',
        'DATI MITTENTE', 'INFORMAZIONI MITTENTE', 'DATI CLIENTE',
        'CLIENTE', 'MITTENTE', 'SENDER NAME', 'SENDER',
        'ORDINANTE', 'REMITENTE', 'NOMINATIVO'
    ]

    for i, linea in enumerate(lineas):
        lu = linea.upper().strip()
        # Si entramos en la sección de beneficiario, dejar de buscar remitente
        if any(b in lu for b in ['DATI DEL BENEFICIARIO', 'BENEFICIARIO', 'DESTINATARIO', 'RECEIVER']):
            break

        for kw in keywords_remitente:
            if kw in lu:
                # Caso A: en la misma línea con dos puntos
                if ':' in linea:
                    val = linea.split(':', 1)[-1].strip()
                    val = re.sub(r'\s*\(\+?\d[\d\s-]+\)\s*$', '', val)
                    if val and len(val) >= 3 and val.upper() != kw:
                        n, a = _split_nombre(val)
                        if n and a:
                            return n, a
                # Caso B: en la misma línea después de la keyword
                elif len(lu) > len(kw) + 3:
                    pos = lu.find(kw) + len(kw)
                    val = linea[pos:].strip().lstrip(':').strip()
                    val = re.sub(r'\s*\(\+?\d[\d\s-]+\)\s*$', '', val)
                    if val and len(val) >= 3 and val.upper() != kw:
                        n, a = _split_nombre(val)
                        if n and a:
                            return n, a

                # Caso C: en las líneas siguientes (1 a 5 líneas)
                etiquetas_stop = [
                    ':', 'BENEFICIARIO', 'IMPORTO', 'TOTALE', 'DESTINATARIO', 'PAGAMENTO',
                    'COMMISSIONE', 'EUR', 'VIA ', 'PIAZZA ', 'TEL', 'NOME', 'COGNOME',
                    'NUMERO', 'DOCUMENTO', 'PASSAPORTO', 'CARTA', 'RICEVUTA', 'TRASFERIMENTO',
                    'DATI', 'INFORMAZIONI', 'CLIENTE', 'MITTENTE', 'SENDER', 'RECEIVER',
                    'INDIRIZZO', 'ADDRESS', 'PAESE', 'COUNTRY', 'STATO', 'CITTA', 'CITTÀ'
                ]
                for j in range(i + 1, min(i + 6, len(lineas))):
                    cand = lineas[j].strip()
                    cand_u = cand.upper()
                    if not cand or any(stop in cand_u for stop in etiquetas_stop):
                        continue
                    n, a = _split_nombre(cand)
                    if n and a:
                        return n, a

    return None, None


def _split_nombre(texto):
    """Separa nombre completo en (nombre, apellido)."""
    texto = texto.strip().strip(':').strip()
    if not texto:
        return None, None

    texto_u = texto.upper()
    etiquetas_rechazar = [
        'NOME E COGNOME', 'NOME COGNOME', 'DATI DEL', 'NUMERO DOCUMENTO',
        'DATI MITTENTE', 'DATI CLIENTE', 'INFORMAZIONI MITTENTE', 'RICEVUTA',
        'TRASFERIMENTO', 'MONEY TRANSFER'
    ]
    if any(lbl in texto_u for lbl in etiquetas_rechazar):
        return None, None

    # Formato "Apellido, Nombre"
    if ',' in texto:
        partes = [p.strip() for p in texto.split(',')]
        if len(partes) == 2:
            return partes[1], partes[0]

    # Palabras que pueden contener letras con tildes o guiones
    palabras = [p for p in texto.split() if re.match(r'^[A-ZÀ-ÿ-]+$', p, re.I) and len(p) > 1]
    # Filtrar palabras que sean números o etiquetas comunes
    palabras = [p for p in palabras if p.upper() not in [
        'TEL', 'DOCUMENTO', 'PASSAPORTO', 'CARTA', 'RIA', 'WU', 'MONEYGRAM',
        'NOME', 'COGNOME', 'DEL', 'DEI', 'DALLA', 'CON', 'PER'
    ]]

    if len(palabras) < 2:
        return None, None

    if len(palabras) == 2:
        return palabras[0], palabras[1]
    elif len(palabras) == 3:
        return palabras[0], ' '.join(palabras[1:])
    else:
        return ' '.join(palabras[:2]), ' '.join(palabras[2:])


def _extraer_documento(lineas):
    """Extrae número de documento del remitente (DNI, NIE, Pasaporte, Carta Identità, CF)."""
    keywords = [
        'NUMERO DEL DOCUMENTO', 'NUMERO DOCUMENTO', 'NUMERO DOC.', 'NUMERO DOC',
        'N. DOCUMENTO', 'N.DOCUMENTO', 'DOC. IDENTITÀ', 'DOC. IDENTITA',
        'DOCUMENTO D\'IDENTITÀ', 'DOCUMENTO D\'IDENTITA', 'TIPO DOCUMENTO',
        'DOCUMENTO', 'DOCUMENT', 'CODICE FISCALE', 'C.F.',
        'NUMERO ID', 'ID NUM', 'ID NUMBER', 'PASAPORTE', 'PASSAPORTO',
        'PASSPORT', 'CARTA IDENTITA', 'CARTA D\'IDENTITÀ', 'NIE', 'DNI'
    ]

    for i, linea in enumerate(lineas):
        lu = linea.upper().strip()
        # Evitar sección de beneficiario
        if any(b in lu for b in ['DATI DEL BENEFICIARIO', 'BENEFICIARIO', 'DESTINATARIO', 'RECEIVER']):
            break

        for kw in keywords:
            if kw in lu:
                val = ''
                if ':' in linea:
                    val = linea.split(':', 1)[-1].strip()
                elif len(lu) > len(kw) + 2:
                    pos = lu.find(kw) + len(kw)
                    val = linea[pos:].strip().lstrip(':').strip()

                # Si no está en la misma línea, buscar en la siguiente línea
                if (not val or len(val) < 4) and i + 1 < len(lineas):
                    cand = lineas[i + 1].strip()
                    if cand and ':' not in cand and len(cand) >= 4:
                        val = cand

                if val and len(val) >= 4:
                    # Limpiar si viene con el tipo antes: "Passaporto 122073848" -> "122073848"
                    partes = val.split()
                    if len(partes) == 2 and len(partes[1]) >= 4:
                        tipos = ['PASSAPORTO', 'CARTA', 'IDENTITA', 'IDENTITÀ', 'NIE', 'DNI', 'PASAPORTE', 'PASSPORT', 'CF', 'C.F.']
                        if any(t in partes[0].upper() for t in tipos):
                            return partes[1].upper()
                    # Quitar caracteres sobrantes comunes
                    val_limpio = re.sub(r'[\(\)\[\]]', '', val).strip()
                    if len(val_limpio) >= 4:
                        return val_limpio.upper()

    return None


def _extraer_telefono(lineas):
    """Extrae teléfono del remitente. Ignora números de agencia."""
    keywords = ['TELEFONO', 'TEL.', 'TEL:', 'TEL ', 'CELLULARE', 'CELL.', 'CELL:', 'MOBILE:', 'PHONE:']
    en_beneficiario = False

    for i, linea in enumerate(lineas):
        lu = linea.upper().strip()
        if any(b in lu for b in ['DATI DEL BENEFICIARIO', 'BENEFICIARIO', 'DESTINATARIO', 'RECEIVER']):
            en_beneficiario = True
        if any(m in lu for m in ['DATI DEL MITTENTE', 'MITTENTE', 'SENDER', 'ORDINANTE']):
            en_beneficiario = False

        if en_beneficiario:
            continue

        for kw in keywords:
            if kw in lu:
                val = ''
                if ':' in linea:
                    val = linea.split(':', 1)[-1].strip()
                elif len(lu) > len(kw) + 4:
                    pos = lu.find(kw) + len(kw)
                    val = linea[pos:].strip().lstrip(':').strip()

                if not val and i + 1 < len(lineas):
                    cand = lineas[i + 1].strip()
                    if re.search(r'\d{7,}', cand):
                        val = cand

                if val:
                    limpio = re.sub(r'[^\d+]', '', val)
                    if 8 <= len(limpio) <= 16:
                        return limpio
    return None


def _extraer_monto(lineas):
    """
    Extrae el monto pagado en EUR.
    Ignora montos en moneda destino (XOF, DOP, etc.).
    """
    # Prioridad 1: Palabras clave de TOTAL (monto final pagado)
    keywords_total = [
        'TOTALE:', 'TOTALE CONTANTE', 'IMPORTO TOTALE PAGATO:',
        'IMPORTO TOTALE:', 'IMPORTO TOTALE', 'TOTAL:', 'TOTALE', 'TOTAL'
    ]
    # Prioridad 2: Monto enviado / importe base
    keywords_base = [
        'IMPORTO INVIATO:', 'IMPORTO INVIATO', 'IMPORTO DI TRASFERIMENTO:',
        'IMPORTO CONTANTE', 'MONTO:', 'AMOUNT:', 'IMPORTO:'
    ]
    # Keywords a ignorar (moneda destino, comisiones, impuestos)
    keywords_ignorar = [
        'IMPORTO DA RICEVERE', 'IMPORTO IN VALUTA LOCALE',
        'INVIATO IN VALUTA', 'TOTALE AL DESTINATARIO',
        'TASSE DI', 'COMMISSIONE', 'TASSO DI', 'TASSO DI CAMBIO',
        'SPREAD', 'ALTRE SPESE', 'IMPOSTA'
    ]

    # Paso 1: Buscar TOTALE
    for i, linea in enumerate(lineas):
        lu = linea.upper()
        if any(ig.upper() in lu for ig in keywords_ignorar):
            continue
        if any(kw.upper() in lu for kw in keywords_total):
            # Probar misma línea
            m = re.search(r'([\d\.,]+)\s*(?:EUR|EURO|€)|(?:EUR|EURO|€)\s*([\d\.,]+)', linea, re.IGNORECASE)
            if m:
                val = m.group(1) or m.group(2)
                parsed = _parse_monto(val)
                if parsed and parsed > 0:
                    return parsed
            # Probar línea siguiente
            if i + 1 < len(lineas):
                cand = lineas[i + 1]
                m_sig = re.search(r'([\d\.,]+)\s*(?:EUR|EURO|€)?|(?:EUR|EURO|€)\s*([\d\.,]+)', cand, re.IGNORECASE)
                if m_sig:
                    val = m_sig.group(1) or m_sig.group(2)
                    parsed = _parse_monto(val)
                    if parsed and parsed > 0:
                        return parsed

    # Paso 2: Buscar IMPORTO BASE
    for i, linea in enumerate(lineas):
        lu = linea.upper()
        if any(ig.upper() in lu for ig in keywords_ignorar):
            continue
        if any(kw.upper() in lu for kw in keywords_base):
            m = re.search(r'([\d\.,]+)\s*(?:EUR|EURO|€)|(?:EUR|EURO|€)\s*([\d\.,]+)', linea, re.IGNORECASE)
            if m:
                val = m.group(1) or m.group(2)
                parsed = _parse_monto(val)
                if parsed and parsed > 0:
                    return parsed
            if i + 1 < len(lineas):
                cand = lineas[i + 1]
                m_sig = re.search(r'([\d\.,]+)\s*(?:EUR|EURO|€)?|(?:EUR|EURO|€)\s*([\d\.,]+)', cand, re.IGNORECASE)
                if m_sig:
                    val = m_sig.group(1) or m_sig.group(2)
                    parsed = _parse_monto(val)
                    if parsed and parsed > 0:
                        return parsed

    # Paso 3: Fallback cualquier línea con EUR/€ que no sea comisión o moneda local
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


def _extraer_referencia(lineas, texto):
    """Extrae código de referencia, MTCN o PIN del recibo."""
    # 1. MTCN específico (WU - 10 dígitos con o sin guiones/espacios)
    m = re.search(r'\bMTCN\s*[:#-]?\s*([0-9]{3,4}[-\s]?[0-9]{3,4}[-\s]?[0-9]{3,4})\b', texto, re.I)
    if m:
        return re.sub(r'[-\s]', '', m.group(1))

    # 2. Palabras clave comunes
    keywords = [
        'CODICE DI RIFERIMENTO', 'CODICE RIFERIMENTO', 'RIFERIMENTO',
        'NUMERO DI RIFERIMENTO', 'PIN', 'TRANSACTION ID', 'NUMERO TRANSAZIONE',
        'N. TRANSAZIONE', 'CODICE SPEDIZIONE', 'CODICE ORDINE', 'REFERENCE NUMBER'
    ]
    for linea in lineas:
        lu = linea.upper()
        for kw in keywords:
            if kw in lu:
                val = linea.split(':', 1)[-1].strip() if ':' in linea else re.sub(re.escape(kw), '', linea, flags=re.I).strip()
                val_limpio = re.sub(r'[^\w-]', '', val)
                if val_limpio and len(val_limpio) >= 6:
                    return val_limpio

    # 3. Fallback: buscar secuencias tipo MTCN o PIN sueltas
    m2 = re.search(r'\b(?:MTCN|PIN|REF)\b\s*[:]?\s*([A-Z0-9-]{6,16})\b', texto, re.I)
    if m2:
        return m2.group(1)

    return None
