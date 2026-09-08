"""
Utilidades para manejar la creación y actualización de clientes con documentos.
Evita duplicados por nombre+apellido y gestiona múltiples documentos por cliente.
"""

from datetime import date, datetime
from app import db
from app.models.cliente import Cliente
from app.models.documento import DocumentoCliente
from app.utils.tenancy import query_negocio


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
    existente = query_negocio(DocumentoCliente).filter(
        DocumentoCliente.cliente_id == cliente.id,
        DocumentoCliente.numero_documento.ilike(numero.strip())
    ).first()
    if existente:
        return existente

    doc = DocumentoCliente(
        negocio_id=cliente.negocio_id,
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
    existente = query_negocio(DocumentoCliente).filter(
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
    doc_mismo_tipo = query_negocio(DocumentoCliente).filter(
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

    # 1. Buscar por documento exacto (la unicidad del documento es por negocio)
    if documento_norm:
        cliente = query_negocio(Cliente).filter(
            Cliente.documento.ilike(documento_norm)
        ).first()

        # Si no se encontró como documento principal, buscar si existe como DocumentoCliente secundario
        if not cliente:
            doc_secundario = query_negocio(DocumentoCliente).filter(
                DocumentoCliente.numero_documento.ilike(documento_norm)
            ).first()
            if doc_secundario and doc_secundario.cliente:
                cliente = doc_secundario.cliente

    # 2. Si no, buscar por nombre+apellido exactos (normalizados)
    if not cliente:
        cliente = query_negocio(Cliente).filter(
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


def fusionar_clientes(cliente_maestro, cliente_duplicado, user_id=None):
    """
    Fusiona un cliente duplicado en un cliente maestro:
    1. Reasigna todas las transacciones de cliente_duplicado a cliente_maestro.
    2. Convierte el documento principal de cliente_duplicado en DocumentoCliente de cliente_maestro.
    3. Reasigna todos los DocumentoCliente de cliente_duplicado a cliente_maestro sin colisiones.
    4. Combina los servicios (M2M) de ambos clientes.
    5. Reasigna o transfiere notificaciones vinculadas.
    6. Registra auditoría en ActivityLog.
    7. Elimina el registro de cliente_duplicado de forma segura.
    """
    from app.models.transaccion import Transaccion, Notificacion
    from app.models.user import ActivityLog

    if cliente_maestro.id == cliente_duplicado.id:
        raise ValueError("No se puede fusionar un cliente consigo mismo.")

    if cliente_maestro.negocio_id != cliente_duplicado.negocio_id:
        raise ValueError("No se pueden fusionar clientes de distintos negocios.")

    # 1. Reasignar todas las transacciones
    Transaccion.query.filter_by(cliente_id=cliente_duplicado.id).update(
        {'cliente_id': cliente_maestro.id},
        synchronize_session=False
    )

    # 2. Reasignar todas las notificaciones
    Notificacion.query.filter_by(cliente_id=cliente_duplicado.id).update(
        {'cliente_id': cliente_maestro.id},
        synchronize_session=False
    )

    # 3. Documento principal del duplicado -> pasarlo a DocumentoCliente del maestro si es distinto
    doc_dup_num = cliente_duplicado.documento.strip().upper() if cliente_duplicado.documento else None
    if doc_dup_num:
        docs_maestro_existentes = {
            cliente_maestro.documento.strip().upper()
        }
        for d in cliente_maestro.documentos:
            docs_maestro_existentes.add(d.numero_documento.strip().upper())

        if doc_dup_num not in docs_maestro_existentes:
            _crear_documento_cliente(
                cliente=cliente_maestro,
                numero=doc_dup_num,
                tipo=cliente_duplicado.tipo_documento,
                fecha_emision=cliente_duplicado.documento_fecha_emision,
                fecha_vencimiento=cliente_duplicado.documento_fecha_vencimiento
            )

    # 4. Reasignar los DocumentoCliente del duplicado
    for doc in list(cliente_duplicado.documentos):
        num_doc = doc.numero_documento.strip().upper()
        # Verificar si cliente_maestro ya lo tiene como principal o secundario
        if num_doc == cliente_maestro.documento.strip().upper():
            db.session.delete(doc)
            continue

        doc_existente = DocumentoCliente.query.filter_by(
            cliente_id=cliente_maestro.id,
            numero_documento=num_doc
        ).first()

        if doc_existente:
            # Si el documento entrante tiene mejor fecha o fotos, enriquecer el existente
            if doc.fecha_vencimiento and (not doc_existente.fecha_vencimiento or doc.fecha_vencimiento > doc_existente.fecha_vencimiento):
                doc_existente.fecha_vencimiento = doc.fecha_vencimiento
                doc_existente.fecha_emision = doc.fecha_emision or doc_existente.fecha_emision
            if doc.foto_anverso and not doc_existente.foto_anverso:
                doc_existente.foto_anverso = doc.foto_anverso
            if doc.foto_reverso and not doc_existente.foto_reverso:
                doc_existente.foto_reverso = doc.foto_reverso
            db.session.delete(doc)
        else:
            doc.cliente_id = cliente_maestro.id
            doc.es_documento_principal = False

    # 5. Combinar servicios M2M
    for serv in cliente_duplicado.servicios:
        if serv not in cliente_maestro.servicios:
            cliente_maestro.servicios.append(serv)

    # 6. Actualizar fecha última visita
    if cliente_duplicado.ultima_visita and (not cliente_maestro.ultima_visita or cliente_duplicado.ultima_visita > cliente_maestro.ultima_visita):
        cliente_maestro.ultima_visita = cliente_duplicado.ultima_visita

    # 7. Completar teléfono si el maestro no tenía
    if not cliente_maestro.telefono and cliente_duplicado.telefono:
        cliente_maestro.telefono = cliente_duplicado.telefono

    # 8. Auditoría
    if user_id:
        log = ActivityLog(
            user_id=user_id,
            activity=f"Fusionó cliente duplicado ID {cliente_duplicado.id} ({cliente_duplicado.nombre_completo()}, doc {cliente_duplicado.documento}) en cliente ID {cliente_maestro.id} ({cliente_maestro.nombre_completo()})"
        )
        db.session.add(log)

    # 9. Eliminar cliente duplicado
    db.session.delete(cliente_duplicado)
    db.session.commit()
    return True


def detectar_posibles_duplicados():
    """
    Busca dentro del negocio actual posibles clientes duplicados
    basándose en coincidencia de (nombre + apellido) o teléfono idéntico.
    Retorna una lista de grupos de duplicados detectados.
    """
    todos = query_negocio(Cliente).order_by(Cliente.id).all()
    
    por_nombre = {}
    por_telefono = {}

    for c in todos:
        # Clave nombre + apellido normalizados
        key_nombre = (_normalizar(c.nombre), _normalizar(c.apellido))
        if key_nombre[0] and key_nombre[1]:
            por_nombre.setdefault(key_nombre, []).append(c)

        # Clave teléfono (solo dígitos, mínimo 7 dígitos)
        if c.telefono:
            tel_digitos = ''.join(ch for ch in c.telefono if ch.isdigit())
            if len(tel_digitos) >= 7:
                por_telefono.setdefault(tel_digitos, []).append(c)

    grupos = []
    ids_procesados = set()

    # Grupos por nombre y apellido
    for (nom, ape), clientes in por_nombre.items():
        if len(clientes) > 1:
            grupo_ids = tuple(sorted(c.id for c in clientes))
            if grupo_ids not in ids_procesados:
                ids_procesados.add(grupo_ids)
                grupos.append({
                    'criterio': f"Mismo nombre y apellido ({clientes[0].nombre_completo()})",
                    'clientes': clientes
                })

    # Grupos por teléfono
    for tel, clientes in por_telefono.items():
        if len(clientes) > 1:
            grupo_ids = tuple(sorted(c.id for c in clientes))
            if grupo_ids not in ids_procesados:
                ids_procesados.add(grupo_ids)
                grupos.append({
                    'criterio': f"Mismo teléfono ({clientes[0].telefono})",
                    'clientes': clientes
                })

    return grupos
