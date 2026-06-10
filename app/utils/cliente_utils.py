"""
Utilidades para manejar la creación y actualización de clientes con documentos.
Evita duplicados por nombre+apellido y gestiona múltiples documentos por cliente.
"""

from datetime import date, datetime
from app import db
from app.models.cliente import Cliente
from app.models.documento import DocumentoCliente


def _normalizar(texto):
    """Normaliza texto para comparación: minúsculas, sin espacios extra."""
    if not texto:
        return ''
    return ' '.join(str(texto).split()).strip().lower()


def _documento_es_mejor(fecha_nueva, fecha_actual):
    """
    Decide si el nuevo documento es "mejor" que el actual.
    Reglas:
    1. Si el nuevo tiene fecha y el actual no → nuevo es mejor
    2. Si ambos tienen fecha → la fecha más reciente gana
    3. Si el actual tiene fecha y el nuevo no → actual es mejor (nuevo no es mejor)
    4. Si ninguno tiene fecha → nuevo es mejor (asumir más reciente)
    """
    if fecha_nueva and not fecha_actual:
        return True
    if not fecha_nueva and fecha_actual:
        return False
    if fecha_nueva and fecha_actual:
        return fecha_nueva > fecha_actual
    # Ninguno tiene fecha
    return True


def _crear_documento_cliente(cliente, numero, tipo, fecha_emision, fecha_vencimiento):
    """Crea un DocumentoCliente asociado al cliente."""
    if not fecha_vencimiento:
        # Fecha lejana como placeholder cuando no se conoce
        fecha_vencimiento = date(2099, 12, 31)

    # Evitar duplicados exactos
    existente = DocumentoCliente.query.filter(
        DocumentoCliente.cliente_id == cliente.id,
        DocumentoCliente.numero_documento.ilike(numero.strip())
    ).first()
    if existente:
        return existente

    doc = DocumentoCliente(
        cliente_id=cliente.id,
        tipo_documento=(tipo or 'OTRO').upper(),
        numero_documento=numero.strip().upper(),
        fecha_emision=fecha_emision,
        fecha_vencimiento=fecha_vencimiento,
        es_documento_principal=False,
        estado='vigente'
    )
    db.session.add(doc)
    db.session.flush()
    return doc


def _mover_documento_principal_a_historial(cliente):
    """Guarda el documento principal actual como DocumentoCliente si no está ya."""
    if not cliente.documento:
        return
    existente = DocumentoCliente.query.filter(
        DocumentoCliente.cliente_id == cliente.id,
        DocumentoCliente.numero_documento.ilike(cliente.documento)
    ).first()
    if existente:
        return
    _crear_documento_cliente(
        cliente,
        cliente.documento,
        cliente.tipo_documento,
        cliente.documento_fecha_emision,
        cliente.documento_fecha_vencimiento
    )


def _manejar_cliente_existente(cliente, documento_nuevo, telefono, tipo_documento,
                               doc_fecha_emision, doc_fecha_vencimiento):
    """
    Lógica interna: el cliente existe, decidir qué hacer con el documento.
    """
    # Actualizar teléfono si viene nuevo
    if telefono and telefono.strip():
        cliente.telefono = telefono.strip()

    doc_nuevo_norm = _normalizar(documento_nuevo)
    doc_principal_norm = _normalizar(cliente.documento)

    # Si el documento es el mismo que el principal, actualizar fechas
    if doc_principal_norm == doc_nuevo_norm:
        if tipo_documento:
            cliente.tipo_documento = tipo_documento.upper()
        if doc_fecha_emision:
            cliente.documento_fecha_emision = doc_fecha_emision
        if doc_fecha_vencimiento:
            cliente.documento_fecha_vencimiento = doc_fecha_vencimiento
        return cliente

    # Documento diferente al principal
    tipo_doc_nuevo = (tipo_documento or 'OTRO').upper()
    tipo_principal = (cliente.tipo_documento or 'OTRO').upper()

    # Buscar si ya hay un documento del mismo tipo en historial
    doc_mismo_tipo = DocumentoCliente.query.filter(
        DocumentoCliente.cliente_id == cliente.id,
        DocumentoCliente.tipo_documento == tipo_doc_nuevo
    ).first()

    principal_mismo_tipo = (tipo_principal == tipo_doc_nuevo)

    # Decidir si el nuevo reemplaza al principal o va al historial
    if principal_mismo_tipo or doc_mismo_tipo:
        # Comparar con el principal (que es del mismo tipo)
        nuevo_es_mejor = _documento_es_mejor(
            doc_fecha_vencimiento,
            cliente.documento_fecha_vencimiento
        )

        if nuevo_es_mejor:
            # Mover principal actual a historial
            _mover_documento_principal_a_historial(cliente)
            # Actualizar principal con el nuevo
            cliente.documento = documento_nuevo.strip().upper()
            cliente.tipo_documento = tipo_doc_nuevo
            if doc_fecha_emision:
                cliente.documento_fecha_emision = doc_fecha_emision
            if doc_fecha_vencimiento:
                cliente.documento_fecha_vencimiento = doc_fecha_vencimiento
        else:
            # El nuevo va como documento secundario
            _crear_documento_cliente(
                cliente, documento_nuevo, tipo_doc_nuevo,
                doc_fecha_emision, doc_fecha_vencimiento
            )
    else:
        # Tipo diferente: agregar como documento adicional
        _crear_documento_cliente(
            cliente, documento_nuevo, tipo_doc_nuevo,
            doc_fecha_emision, doc_fecha_vencimiento
        )

    return cliente


def obtener_o_crear_cliente_con_documento(
    nombre, apellido, documento, telefono=None,
    tipo_documento=None, fecha_nacimiento=None,
    doc_fecha_emision=None, doc_fecha_vencimiento=None
):
    """
    Busca un cliente por documento o por nombre+apellido.
    Si existe con otro documento, lo agrega como DocumentoCliente.
    Si es el mismo tipo de documento, decide cuál quedarse según fechas.

    Retorna: (cliente, es_nuevo_boolean)
    """
    nombre_norm = _normalizar(nombre)
    apellido_norm = _normalizar(apellido)
    documento_norm = _normalizar(documento)

    if not nombre_norm or not apellido_norm or not documento_norm:
        raise ValueError("Nombre, apellido y documento son obligatorios")

    cliente = None

    # 1. Buscar por documento exacto
    if documento_norm:
        cliente = Cliente.query.filter(
            Cliente.documento.ilike(documento_norm)
        ).first()

    # 2. Si no, buscar por nombre+apellido exactos (normalizados)
    if not cliente:
        cliente = Cliente.query.filter(
            db.func.lower(db.func.trim(Cliente.nombre)) == nombre_norm,
            db.func.lower(db.func.trim(Cliente.apellido)) == apellido_norm
        ).first()

    if cliente:
        # Cliente existente: manejar documento
        _manejar_cliente_existente(
            cliente, documento, telefono, tipo_documento,
            doc_fecha_emision, doc_fecha_vencimiento
        )
        return cliente, False

    # Cliente nuevo
    nuevo = Cliente(
        nombre=nombre.strip().title(),
        apellido=apellido.strip().title(),
        documento=documento.strip().upper(),
        telefono=telefono or None,
        fecha_nacimiento=fecha_nacimiento or date(1990, 1, 1),
        tipo_documento=(tipo_documento or 'NIE').upper(),
        documento_fecha_emision=doc_fecha_emision,
        documento_fecha_vencimiento=doc_fecha_vencimiento,
        ultima_visita=datetime.utcnow()
    )
    db.session.add(nuevo)
    db.session.flush()
    return nuevo, True
