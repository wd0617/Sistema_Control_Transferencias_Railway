"""
Parser inteligente de recibos de transferencias.
Soporta texto copiado desde Western Union, MoneyGram, Ria, etc.
"""

import re


def parsear_recibo(texto):
    """
    Recibe texto crudo de un recibo y devuelve dict con datos extraídos.
    Campos devueltos: nombre, apellido, documento, telefono, monto, moneda,
    referencia, servicio (inferido), raw_nombre, lineas_nombre.
    """
    if not texto:
        return {}

    texto = texto.strip()
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    texto_upper = texto.upper()
    resultado = {}

    # --- Detectar servicio (hint) ---
    servicios_hints = [
        ('Western Union', ['WESTERN UNION', 'WU ', 'WESTERNUNION']),
        ('MoneyGram', ['MONEYGRAM', 'MONEY GRAM']),
        ('Ria', ['RIA MONEY', 'RIA ', 'RIAMONEY']),
        ('Mondial Bony', ['MONDIAL', 'BONY']),
        ('Monty', ['MONTY']),
    ]
    for serv_nombre, hints in servicios_hints:
        for h in hints:
            if h in texto_upper:
                resultado['servicio_hint'] = serv_nombre
                break
        if resultado.get('servicio_hint'):
            break

    # --- Referencia / MTCN / PIN ---
    ref_patterns = [
        r'(?:MTCN|REFERENCE|REF\.?\s*NO|PIN|CONTROL|NUMERO|NÚMERO)\s*[:#]?\s*(\d{8,12})',
        r'(?:MTCN|REFERENCE)\s*[:#]?\s*(\d[\d\s-]{6,14}\d)',
    ]
    for pat in ref_patterns:
        m = re.search(pat, texto_upper)
        if m:
            resultado['referencia'] = re.sub(r'\s+', '', m.group(1))
            break

    # --- Monto ---
    monto = None
    moneda = None
    # Patrones tipo "Amount: 1,234.56 EUR" o "Monto: 1.234,56 €"
    monto_patterns = [
        r'(?:AMOUNT|SEND\s*AMOUNT|MONTO|TOTAL|CANTIDAD)\s*[:]?\s*([\d\.,]+)\s*([A-Z€$]{1,3})?',
        r'([\d\.,]+)\s*(?:EUR|USD|GBP|€|\$)\s*(?:AMOUNT|MONTO)?',
        r'(?:EUR|USD|GBP|€|\$)\s*([\d\.,]+)',
    ]
    for pat in monto_patterns:
        m = re.search(pat, texto_upper)
        if m:
            raw_str = m.group(1)
            raw = _parse_monto(raw_str)
            if raw is not None:
                resultado['monto'] = round(raw, 2)
                break

    # Detectar moneda
    if 'EUR' in texto_upper or '€' in texto:
        resultado['moneda'] = 'EUR'
    elif 'USD' in texto_upper or '$' in texto:
        resultado['moneda'] = 'USD'
    elif 'GBP' in texto_upper or '£' in texto:
        resultado['moneda'] = 'GBP'

    # --- Documento / ID ---
    doc_patterns = [
        r'(?:ID|DNI|PASSPORT|PASAPORTE|DOCUMENTO|DOC\.?\s*NO)\s*[:#]?\s*([A-Z0-9]{5,20})',
        r'(?:ID|DNI)\s*[:]?\s*([0-9]{7,10}[A-Z]?)',
    ]
    for pat in doc_patterns:
        m = re.search(pat, texto_upper)
        if m:
            resultado['documento'] = m.group(1).strip()
            break
    if not resultado.get('documento'):
        # Fallback: buscar número suelto de 7-10 dígitos que no sea monto ni referencia
        candidatos = re.findall(r'\b([0-9]{7,10})\b', texto)
        for c in candidatos:
            if c != str(int(resultado.get('monto', 0))) and c != resultado.get('referencia', ''):
                resultado['documento'] = c
                break

    # --- Teléfono ---
    tel_match = re.search(r'(?:TEL|TELEFONO|TELÉFONO|PHONE|MOBILE)\s*[:]?\s*([+\d\s()-]{7,20})', texto_upper)
    if tel_match:
        resultado['telefono'] = re.sub(r'[^\d+]', '', tel_match.group(1))
    else:
        # Buscar número español/europeo suelto
        tel_match = re.search(r'\b(\+?\d[\d\s]{8,14}\d)\b', texto)
        if tel_match:
            limpio = re.sub(r'[^\d+]', '', tel_match.group(1))
            if len(limpio) >= 9:
                resultado['telefono'] = limpio

    # --- Nombre ---
    nombre, apellido = extraer_nombre(lineas, texto_upper)
    if nombre:
        resultado['nombre'] = nombre
        resultado['apellido'] = apellido or ''
        resultado['raw_nombre'] = f"{nombre} {apellido}".strip()

    return resultado


def extraer_nombre(lineas, texto_upper):
    """
    Intenta extraer nombre y apellido del recibo.
    Busca palabras clave como Sender, Remitente, From, Name, y también
    heurísticas sobre líneas con 2-4 palabras en mayúsculas.
    """
    nombre_keywords = ['SENDER', 'REMITENTE', 'FROM', 'SEND BY', 'ENVIA', 'NAME', 'NOMBRE',
                       'CUSTOMER', 'CLIENTE', 'SENDER NAME', 'REMITENTE NAME']

    # Estrategia 1: buscar línea justo después de keyword
    for i, linea in enumerate(lineas):
        linea_upper = linea.upper()
        for kw in nombre_keywords:
            if kw in linea_upper:
                # Si la keyword está sola en la línea, tomar la siguiente
                if len(linea_upper.replace(kw, '').strip()) <= 2:
                    if i + 1 < len(lineas):
                        candidato = lineas[i + 1]
                        parsed = parsear_nombre_completo(candidato)
                        if parsed:
                            return parsed
                else:
                    # La keyword y el nombre están en la misma línea
                    resto = linea_upper.split(kw, 1)[-1].strip(':').strip()
                    parsed = parsear_nombre_completo(resto)
                    if parsed:
                        return parsed

    # Estrategia 2: buscar líneas que parezcan nombres completos (2-4 palabras, mayúsculas)
    for linea in lineas:
        palabras = linea.split()
        if 2 <= len(palabras) <= 4:
            # Debe tener al menos 2 palabras puramente alfabéticas
            alfabeticas = [p for p in palabras if p.isalpha() and len(p) > 1]
            if len(alfabeticas) >= 2:
                # Descartar si parece dirección, calle, etc.
                descartar = ['STREET', 'AVENUE', 'CALLE', 'AVDA', 'C/', 'PLAZA',
                             'BANK', 'BANCO', 'AGENT', 'OFFICE', 'SUCURSAL',
                             'AMOUNT', 'TOTAL', 'FEE', 'COMISION', 'DATE', 'FECHA',
                             'REFERENCE', 'MTCN', 'PHONE', 'TEL', 'EMAIL', 'ID',
                             'DNI', 'PASSPORT', 'ADDRESS', 'DIRECCION']
                if not any(d in linea.upper() for d in descartar):
                    parsed = parsear_nombre_completo(linea)
                    if parsed:
                        return parsed

    return None, None


def _parse_monto(raw_str):
    """
    Convierte un string de monto a float, manejando formatos europeos e ingleses.
    Ejemplos: '500.00' -> 500.0, '1.250,00' -> 1250.0, '1,250.00' -> 1250.0
    """
    if not raw_str:
        return None
    s = raw_str.strip()
    has_dot = '.' in s
    has_comma = ',' in s

    if has_dot and has_comma:
        # Ambos: determinar cuál es el separador decimal (el último)
        last_dot = s.rfind('.')
        last_comma = s.rfind(',')
        if last_comma > last_dot:
            # Europeo: 1.250,00
            s = s.replace('.', '').replace(',', '.')
        else:
            # Inglés: 1,250.00
            s = s.replace(',', '')
    elif has_comma:
        # Solo coma: puede ser decimal europeo (1250,00) o separador de miles (1,250)
        parts = s.split(',')
        if len(parts) == 2 and len(parts[-1]) <= 2:
            # Decimal europeo
            s = s.replace(',', '.')
        else:
            # Separador de miles
            s = s.replace(',', '')
    elif has_dot:
        # Solo punto: puede ser decimal (500.00) o separador de miles (1.250)
        parts = s.split('.')
        if len(parts) == 2 and len(parts[-1]) <= 2:
            # Decimal
            pass  # s ya está bien
        else:
            # Separador de miles
            s = s.replace('.', '')

    try:
        return float(s)
    except ValueError:
        return None


def parsear_nombre_completo(texto):
    """
    Separa un texto tipo 'DIANA KAZARYAN' o 'KAZARYAN, DIANA' en nombre y apellido.
    Devuelve (nombre, apellido) o None si no parece un nombre válido.
    """
    texto = texto.strip().strip(':').strip()
    if not texto:
        return None, None

    # Formato "Apellido, Nombre"
    if ',' in texto:
        partes = [p.strip() for p in texto.split(',')]
        if len(partes) == 2:
            return partes[1], partes[0]

    palabras = texto.split()
    # Filtrar palabras no alfabéticas
    palabras = [p for p in palabras if p.isalpha() and len(p) > 1]

    if len(palabras) < 2:
        return None, None

    # Nombre = primera palabra (o primeras 2 si son cortas)
    # Apellido = resto
    if len(palabras) == 2:
        return palabras[0], palabras[1]
    elif len(palabras) == 3:
        # Probable: nombre + 2 apellidos
        return palabras[0], ' '.join(palabras[1:])
    else:
        # 4+ palabras: tomar primeras 2 como nombre, resto como apellido (o ajustar)
        return ' '.join(palabras[:2]), ' '.join(palabras[2:])
