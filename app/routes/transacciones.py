import re
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.models.cliente import Cliente, Servicio
from app.models.transaccion import Transaccion
from app import db
from app.extensions import csrf
from app.utils.tenancy import query_negocio, get_negocio_o_404, current_negocio_id
from datetime import datetime, timedelta
from sqlalchemy import func, desc, or_

transacciones = Blueprint('transacciones', __name__)

@transacciones.route('/')
@login_required
def lista():
    # Fechas para filtrados (usando rangos datetime compatibles con PostgreSQL y SQLite)
    hoy = datetime.now().date()
    inicio_dia = datetime.combine(hoy, datetime.min.time())
    fin_dia = datetime.combine(hoy, datetime.max.time())
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_semana_dt = datetime.combine(inicio_semana, datetime.min.time())
    inicio_mes = datetime(hoy.year, hoy.month, 1).date()
    inicio_mes_dt = datetime.combine(inicio_mes, datetime.min.time())
    fecha_limite = hoy - timedelta(days=30)
    fecha_limite_dt = datetime.combine(fecha_limite, datetime.min.time())
    
    # Filtro por negocio para los agregados globales (None = superadmin sin modo soporte)
    nid = current_negocio_id()
    filtro_negocio = [Transaccion.negocio_id == nid] if nid is not None else []

    # Estadísticas rápidas en SQL puro (sin cargar objetos completos)
    stats_hoy = db.session.query(
        func.count(Transaccion.id),
        func.coalesce(func.sum(Transaccion.monto), 0),
        func.coalesce(func.sum(Transaccion.comision), 0)
    ).filter(Transaccion.fecha >= inicio_dia, Transaccion.fecha <= fin_dia, *filtro_negocio).first()

    stats_semana = db.session.query(
        func.count(Transaccion.id),
        func.coalesce(func.sum(Transaccion.monto), 0),
        func.coalesce(func.sum(Transaccion.comision), 0)
    ).filter(Transaccion.fecha >= inicio_semana_dt, *filtro_negocio).first()

    stats_mes = db.session.query(
        func.count(Transaccion.id),
        func.coalesce(func.sum(Transaccion.monto), 0),
        func.coalesce(func.sum(Transaccion.comision), 0)
    ).filter(Transaccion.fecha >= inicio_mes_dt, *filtro_negocio).first()

    # Top clientes frecuentes (últimos 30 días)
    clientes_frecuentes = db.session.query(
        Cliente,
        func.count(Transaccion.id).label('total_transacciones')
    ).join(Transaccion).filter(
        Transaccion.fecha >= fecha_limite_dt,
        *filtro_negocio
    ).group_by(
        Cliente.id
    ).order_by(
        desc(func.count(Transaccion.id))
    ).limit(5).all()
    
    estadisticas = {
        'transacciones_hoy': stats_hoy[0],
        'transacciones_semana': stats_semana[0],
        'transacciones_mes': stats_mes[0],
        'monto_total_hoy': float(stats_hoy[1]),
        'comision_total_hoy': float(stats_hoy[2]),
        'monto_total_semana': float(stats_semana[1]),
        'comision_total_semana': float(stats_semana[2]),
        'monto_total_mes': float(stats_mes[1]),
        'comision_total_mes': float(stats_mes[2]),
        'clientes_frecuentes': clientes_frecuentes
    }
    
    # Paginación de transacciones (50 por página) con eager loading
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    pagination = query_negocio(Transaccion).options(
        joinedload(Transaccion.cliente),
        joinedload(Transaccion.servicio)
    ).order_by(Transaccion.fecha.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('transacciones/lista.html', 
                          transacciones=pagination.items,
                          pagination=pagination,
                          estadisticas=estadisticas,
                          now=datetime.now())

@transacciones.route('/cliente/<int:cliente_id>')
@login_required
def cliente_historial(cliente_id):
    cliente = get_negocio_o_404(Cliente, cliente_id)
    transacciones = query_negocio(Transaccion).options(
        joinedload(Transaccion.servicio)
    ).filter_by(cliente_id=cliente_id).order_by(Transaccion.fecha.desc()).all()
    saldo_disponible = cliente.calcular_saldo_disponible()
    dias_reestablecimiento = cliente.dias_hasta_reestablecimiento()
    
    return render_template('transacciones/cliente_historial.html', 
                          cliente=cliente, 
                          transacciones=transacciones,
                          saldo_disponible=saldo_disponible,
                          dias_reestablecimiento=dias_reestablecimiento,
                          now=datetime.now())

@transacciones.route('/nueva', methods=['GET', 'POST'])
@login_required
def nueva():
    # Si llega con un cliente preseleccionado
    cliente_id = request.args.get('cliente_id', None)
    cliente = None
    
    if cliente_id:
        cliente = get_negocio_o_404(Cliente, cliente_id)
    
    if request.method == 'POST':
        # Obtener datos del formulario
        cliente_id = request.form.get('cliente_id')
        servicio_id = request.form.get('servicio_id')
        monto = request.form.get('monto')
        comision = request.form.get('comision')
        descripcion = request.form.get('descripcion')
        
        # Validaciones
        if not cliente_id or not servicio_id or not monto:
            flash('Todos los campos con * son obligatorios', 'danger')
            return redirect(url_for('transacciones.nueva', cliente_id=cliente_id))
        
        # Convertir valores numéricos
        try:
            monto = float(monto)
            comision = float(comision) if comision else 0
        except ValueError:
            flash('Los montos deben ser valores numéricos válidos', 'danger')
            return redirect(url_for('transacciones.nueva', cliente_id=cliente_id))
        
        # Verificar cliente y servicio (solo del negocio actual)
        cliente = get_negocio_o_404(Cliente, cliente_id)
        servicio = get_negocio_o_404(Servicio, servicio_id)
        
        if not cliente or not servicio:
            flash('Cliente o servicio no válido', 'danger')
            return redirect(url_for('transacciones.nueva'))
        
        # Verificar límite de transacciones
        saldo_disponible = cliente.calcular_saldo_disponible()
        if monto > saldo_disponible:
            flash(f'El monto excede el límite disponible de {saldo_disponible}€ para este cliente', 'danger')
            return redirect(url_for('transacciones.nueva', cliente_id=cliente_id))
        
        # Crear transacción
        nueva_transaccion = Transaccion(
            cliente_id=cliente_id,
            servicio_id=servicio_id,
            monto=monto,
            comision=comision,
            notas=descripcion,
            fecha=datetime.now(),
            creado_por=current_user.id
        )
        
        db.session.add(nueva_transaccion)
        
        # Actualizar última visita del cliente
        cliente.ultima_visita = datetime.now()
        
        db.session.commit()
        flash('Transacción registrada correctamente', 'success')
        
        # Redireccionar al historial del cliente
        return redirect(url_for('transacciones.cliente_historial', cliente_id=cliente_id))
    
    # GET: Mostrar formulario
    clientes = query_negocio(Cliente).all()
    servicios = query_negocio(Servicio).filter_by(activo=True).all()
    
    # Si hay un cliente preseleccionado, calculamos su saldo disponible
    saldo_disponible = None
    if cliente:
        saldo_disponible = cliente.calcular_saldo_disponible()
    
    return render_template('transacciones/nueva.html', 
                          clientes=clientes, 
                          servicios=servicios, 
                          cliente_seleccionado=cliente,
                          saldo_disponible=saldo_disponible,
                          now=datetime.now())

@transacciones.route('/editar/<int:transaccion_id>', methods=['GET', 'POST'])
@login_required
def editar(transaccion_id):
    # Obtener la transacción existente (solo del negocio actual)
    transaccion = get_negocio_o_404(Transaccion, transaccion_id)
    
    # Si es un POST, actualizar la transacción
    if request.method == 'POST':
        # Obtener datos del formulario
        servicio_id = request.form.get('servicio_id')
        monto = request.form.get('monto')
        comision = request.form.get('comision')
        descripcion = request.form.get('descripcion')
        
        # Validaciones
        if not servicio_id or not monto:
            flash('Todos los campos con * son obligatorios', 'danger')
            return redirect(url_for('transacciones.editar', transaccion_id=transaccion_id))
        
        # Convertir valores numéricos
        try:
            monto = float(monto)
            comision = float(comision) if comision else 0
        except ValueError:
            flash('Los montos deben ser valores numéricos válidos', 'danger')
            return redirect(url_for('transacciones.editar', transaccion_id=transaccion_id))
        
        # Verificar servicio (solo del negocio actual)
        servicio = get_negocio_o_404(Servicio, servicio_id)
        
        if not servicio:
            flash('Servicio no válido', 'danger')
            return redirect(url_for('transacciones.editar', transaccion_id=transaccion_id))
        
        # Actualizar transacción
        transaccion.servicio_id = servicio_id
        transaccion.monto = monto
        transaccion.comision = comision
        transaccion.notas = descripcion
        
        db.session.commit()
        flash('Transacción actualizada correctamente', 'success')
        
        # Redireccionar al historial del cliente
        return redirect(url_for('transacciones.cliente_historial', cliente_id=transaccion.cliente_id))
    
    # GET: Mostrar formulario con datos de la transacción
    servicios = query_negocio(Servicio).filter_by(activo=True).all()
    
    return render_template('transacciones/editar.html', 
                          transaccion=transaccion,
                          servicios=servicios,
                          now=datetime.now())


@transacciones.route('/registro-rapido', methods=['GET', 'POST'])
@login_required
def registro_rapido():
    """Formulario ultra-rápido: 5 campos, autocompletado, guardar de una."""
    from datetime import date
    
    servicios = query_negocio(Servicio).filter_by(activo=True).all()
    
    if request.method == 'POST':
        cliente_id = request.form.get('cliente_id', type=int)
        documento = request.form.get('documento', '').strip()
        nombre = request.form.get('nombre', '').strip()
        apellido = request.form.get('apellido', '').strip()
        telefono = request.form.get('telefono', '').strip()
        servicio_id = request.form.get('servicio_id', type=int)
        monto_str = request.form.get('monto', '').strip()
        
        servicio = get_negocio_o_404(Servicio, servicio_id) if servicio_id else None
        if not servicio:
            flash('Seleccioná un servicio', 'danger')
            return redirect(url_for('transacciones.registro_rapido'))
        
        try:
            monto = float(monto_str.replace(',', '.'))
        except ValueError:
            flash('El monto no es válido', 'danger')
            return redirect(url_for('transacciones.registro_rapido'))
        
        cliente = None
        if cliente_id:
            cliente = get_negocio_o_404(Cliente, cliente_id)

        if not cliente:
            if not nombre or not apellido or not documento:
                flash('Faltan datos del cliente', 'danger')
                return redirect(url_for('transacciones.registro_rapido'))
            from app.utils.cliente_utils import obtener_o_crear_cliente_con_documento
            cliente, es_nuevo = obtener_o_crear_cliente_con_documento(
                nombre=nombre,
                apellido=apellido,
                documento=documento,
                telefono=telefono,
                fecha_nacimiento=date(1990, 1, 1)
            )
            if es_nuevo:
                cliente.servicios.append(servicio)

        if cliente:
            cliente.ultima_visita = datetime.utcnow()
            if servicio not in cliente.servicios:
                cliente.servicios.append(servicio)
        
        # Anti-duplicado
        desde = datetime.utcnow() - timedelta(hours=24)
        dup = query_negocio(Transaccion).filter(
            Transaccion.cliente_id == cliente.id,
            Transaccion.servicio_id == servicio.id,
            Transaccion.monto == monto,
            Transaccion.fecha >= desde
        ).first()
        if dup:
            flash(f'⚠️ Ya existe esta transacción ({cliente.nombre_completo()} - {monto:.2f}€). '
                  f'<a href="{url_for("transacciones.nueva", cliente_id=cliente.id)}">Click acá</a> si querés forzarla.',
                  'warning')
            return redirect(url_for('transacciones.registro_rapido'))
        
        comision = round(monto * (servicio.comision_porcentaje or 0) / 100, 2)
        referencia = request.form.get('referencia', '').strip()
        tx = Transaccion(
            cliente_id=cliente.id,
            servicio_id=servicio.id,
            monto=monto,
            comision=comision,
            referencia=referencia or None,
            creado_por=current_user.id
        )
        db.session.add(tx)
        db.session.commit()

        from app.utils.whatsapp_utils import generar_url_whatsapp
        session['ultimo_envio'] = {
            'id': tx.id,
            'cliente': cliente.nombre_completo(),
            'telefono': cliente.telefono or '',
            'monto': f"{monto:.2f}",
            'servicio': servicio.nombre,
            'referencia': referencia or '',
            'wa_url_it': generar_url_whatsapp(tx, idioma='it'),
            'wa_url_es': generar_url_whatsapp(tx, idioma='es')
        }
        flash(f'✅ {cliente.nombre_completo()} — {monto:.2f}€ ({servicio.nombre})', 'success')
        return redirect(url_for('transacciones.registro_rapido'))
    
    ultimo_envio = session.pop('ultimo_envio', None)
    return render_template('transacciones/registro_rapido.html', servicios=servicios, ultimo_envio=ultimo_envio)


@transacciones.route('/<int:transaccion_id>/whatsapp')
@login_required
def whatsapp_redirect(transaccion_id):
    """Redirige al enlace de WhatsApp de una transacción."""
    transaccion = get_negocio_o_404(Transaccion, transaccion_id)
    lang = request.args.get('lang', 'it')
    from app.utils.whatsapp_utils import generar_url_whatsapp
    url = generar_url_whatsapp(transaccion, idioma=lang)
    return redirect(url)


@transacciones.route('/api/buscar-cliente')
@login_required
def api_buscar_cliente():
    """AJAX: busca clientes por documento (principal o secundario), nombre o teléfono."""
    from app.models.documento import DocumentoCliente
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return {'resultados': []}
    
    like = f'%{q}%'
    # Buscar IDs de clientes cuyos documentos secundarios coincidan
    doc_cliente_ids = query_negocio(DocumentoCliente).filter(
        DocumentoCliente.numero_documento.ilike(like)
    ).with_entities(DocumentoCliente.cliente_id).subquery()

    # Siempre acotado al negocio actual (lo usa el registro rápido y la extensión)
    clientes = query_negocio(Cliente).filter(
        or_(
            Cliente.documento.ilike(like),
            Cliente.id.in_(doc_cliente_ids),
            Cliente.nombre.ilike(like),
            Cliente.apellido.ilike(like),
            Cliente.telefono.ilike(like)
        )
    ).limit(10).all()
    
    resultados = []
    for c in clientes:
        # Detectar si coincidió por documento secundario
        coincidencia_sec = None
        docs_secundarios = []
        for d in c.documentos:
            docs_secundarios.append(f"{d.tipo_documento}: {d.numero_documento}")
            if q.lower() in d.numero_documento.lower():
                coincidencia_sec = f"{d.tipo_documento} {d.numero_documento}"

        resultados.append({
            'id': c.id,
            'documento': c.documento,
            'tipo_documento': c.tipo_documento or 'NIE',
            'nombre': c.nombre,
            'apellido': c.apellido,
            'telefono': c.telefono or '',
            'coincidencia_secundaria': coincidencia_sec,
            'documentos_adicionales': docs_secundarios
        })
    
    return {'resultados': resultados}


@transacciones.route('/api/negocio-info')
@csrf.exempt
def api_negocio_info():
    """Devuelve datos del negocio activo o identificado por id/slug para la extensión."""
    from app.models.negocio import Negocio
    if not current_user or not current_user.is_authenticated:
        return jsonify({
            'ok': False,
            'autenticado': False,
            'mensaje': 'No has iniciado sesión en el sistema.'
        }), 401

    nid = current_negocio_id()
    negocio = Negocio.query.get(nid) if nid else None

    # Si es superadmin y no tiene negocio fijado, asociar al primer negocio aprobado
    if not negocio and current_user.is_superadmin:
        negocio = Negocio.query.filter_by(estado='aprobado').first()
        if negocio:
            session['negocio_vista'] = negocio.id

    if not negocio:
        return jsonify({
            'ok': False,
            'autenticado': True,
            'usuario': current_user.username,
            'negocio': None,
            'mensaje': 'No hay un negocio seleccionado o asignado.'
        })

    return jsonify({
        'ok': True,
        'autenticado': True,
        'usuario': current_user.username,
        'es_superadmin': current_user.is_superadmin,
        'negocio': {
            'id': negocio.id,
            'nombre': negocio.nombre,
            'slug': negocio.slug,
            'estado': negocio.estado
        }
    })


@transacciones.route('/api/analizar-recibo', methods=['POST'])
@csrf.exempt
@login_required
def api_analizar_recibo():
    """AJAX: recibe texto de recibo y devuelve JSON con datos extraídos."""
    from app.utils.parse_recibo import parsear_recibo
    data = request.get_json() or {}
    texto = data.get('texto', '')
    resultado = parsear_recibo(texto)
    return resultado


@transacciones.route('/api/verificar-cliente')
@csrf.exempt
@login_required
def api_verificar_cliente():
    """AJAX: verifica estado, saldo disponible semanal y vigencia de documento del cliente."""
    from app.models.documento import DocumentoCliente
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return {'clientes': []}

    like = f'%{q}%'
    doc_cliente_ids = query_negocio(DocumentoCliente).filter(
        DocumentoCliente.numero_documento.ilike(like)
    ).with_entities(DocumentoCliente.cliente_id).subquery()

    clientes = query_negocio(Cliente).filter(
        or_(
            Cliente.documento.ilike(like),
            Cliente.id.in_(doc_cliente_ids),
            Cliente.nombre.ilike(like),
            Cliente.apellido.ilike(like),
            Cliente.telefono.ilike(like)
        )
    ).limit(6).all()

    limite = current_app.config.get('LIMITE_TRANSFERENCIA_SEMANAL', 999.0)
    resultados = []
    for c in clientes:
        saldo = c.calcular_saldo_disponible(limite_semanal=limite)
        dias_rest = c.dias_hasta_reestablecimiento()
        estado_doc = c.estado_documento
        dias_venc = c.dias_hasta_vencimiento
        puede_enviar = (saldo > 0 and estado_doc != 'vencido')

        docs_extras = [{
            'tipo': d.tipo_documento,
            'numero': d.numero_documento,
            'estado': d.estado
        } for d in c.documentos]

        resultados.append({
            'id': c.id,
            'nombre_completo': c.nombre_completo(),
            'nombre': c.nombre,
            'apellido': c.apellido,
            'documento': c.documento,
            'tipo_documento': c.tipo_documento or 'NIE',
            'telefono': c.telefono or '',
            'saldo_disponible': round(max(0.0, saldo), 2),
            'limite_semanal': limite,
            'dias_reestablecimiento': dias_rest,
            'estado_documento': estado_doc,
            'dias_hasta_vencimiento': dias_venc,
            'puede_enviar': puede_enviar,
            'total_transacciones': c.transacciones.count(),
            'documentos_adicionales': docs_extras
        })

    return {'clientes': resultados}

