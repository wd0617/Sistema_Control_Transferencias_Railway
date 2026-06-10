import re
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.models.cliente import Cliente, Servicio
from app.models.transaccion import Transaccion
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, desc, or_

transacciones = Blueprint('transacciones', __name__)

@transacciones.route('/')
@login_required
def lista():
    # Fechas para filtrados
    hoy = datetime.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_mes = datetime(hoy.year, hoy.month, 1).date()
    fecha_limite = hoy - timedelta(days=30)
    
    # Estadísticas rápidas en SQL puro (sin cargar objetos completos)
    stats_hoy = db.session.query(
        func.count(Transaccion.id),
        func.coalesce(func.sum(Transaccion.monto), 0),
        func.coalesce(func.sum(Transaccion.comision), 0)
    ).filter(func.date(Transaccion.fecha) == hoy).first()
    
    stats_semana = db.session.query(
        func.count(Transaccion.id),
        func.coalesce(func.sum(Transaccion.monto), 0),
        func.coalesce(func.sum(Transaccion.comision), 0)
    ).filter(func.date(Transaccion.fecha) >= inicio_semana).first()
    
    stats_mes = db.session.query(
        func.count(Transaccion.id),
        func.coalesce(func.sum(Transaccion.monto), 0),
        func.coalesce(func.sum(Transaccion.comision), 0)
    ).filter(func.date(Transaccion.fecha) >= inicio_mes).first()
    
    # Top clientes frecuentes (últimos 30 días)
    clientes_frecuentes = db.session.query(
        Cliente,
        func.count(Transaccion.id).label('total_transacciones')
    ).join(Transaccion).filter(
        func.date(Transaccion.fecha) >= fecha_limite
    ).group_by(
        Cliente.id
    ).order_by(
        desc('total_transacciones')
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
    
    pagination = Transaccion.query.options(
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
    cliente = Cliente.query.get_or_404(cliente_id)
    transacciones = Transaccion.query.options(
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
        cliente = Cliente.query.get_or_404(cliente_id)
    
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
        
        # Verificar cliente y servicio
        cliente = Cliente.query.get(cliente_id)
        servicio = Servicio.query.get(servicio_id)
        
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
    clientes = Cliente.query.all()
    servicios = Servicio.query.filter_by(activo=True).all()
    
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
    # Obtener la transacción existente
    transaccion = Transaccion.query.get_or_404(transaccion_id)
    
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
        
        # Verificar servicio
        servicio = Servicio.query.get(servicio_id)
        
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
    servicios = Servicio.query.filter_by(activo=True).all()
    
    return render_template('transacciones/editar.html', 
                          transaccion=transaccion,
                          servicios=servicios,
                          now=datetime.now())


@transacciones.route('/registro-rapido', methods=['GET', 'POST'])
@login_required
def registro_rapido():
    """Formulario ultra-rápido: 5 campos, autocompletado, guardar de una."""
    from datetime import date
    
    servicios = Servicio.query.filter_by(activo=True).all()
    
    if request.method == 'POST':
        cliente_id = request.form.get('cliente_id', type=int)
        documento = request.form.get('documento', '').strip()
        nombre = request.form.get('nombre', '').strip()
        apellido = request.form.get('apellido', '').strip()
        telefono = request.form.get('telefono', '').strip()
        servicio_id = request.form.get('servicio_id', type=int)
        monto_str = request.form.get('monto', '').strip()
        
        servicio = Servicio.query.get(servicio_id) if servicio_id else None
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
            cliente = Cliente.query.get(cliente_id)

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
        dup = Transaccion.query.filter(
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
        db.session.add(Transaccion(
            cliente_id=cliente.id,
            servicio_id=servicio.id,
            monto=monto,
            comision=comision,
            creado_por=current_user.id
        ))
        db.session.commit()
        flash(f'✅ {cliente.nombre_completo()} — {monto:.2f}€ ({servicio.nombre})', 'success')
        return redirect(url_for('transacciones.registro_rapido'))
    
    return render_template('transacciones/registro_rapido.html', servicios=servicios)


@transacciones.route('/api/buscar-cliente')
@login_required
def api_buscar_cliente():
    """AJAX: busca clientes por documento, nombre o teléfono."""
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return {'resultados': []}
    
    like = f'%{q}%'
    clientes = Cliente.query.filter(
        or_(
            Cliente.documento.ilike(like),
            Cliente.nombre.ilike(like),
            Cliente.apellido.ilike(like),
            Cliente.telefono.ilike(like)
        )
    ).limit(8).all()
    
    return {
        'resultados': [
            {'id': c.id, 'documento': c.documento, 'nombre': c.nombre,
             'apellido': c.apellido, 'telefono': c.telefono or ''}
            for c in clientes
        ]
    }


@transacciones.route('/api/analizar-recibo', methods=['POST'])
@login_required
def api_analizar_recibo():
    """AJAX: recibe texto de recibo y devuelve JSON con datos extraídos."""
    from app.utils.parse_recibo import parsear_recibo
    data = request.get_json() or {}
    texto = data.get('texto', '')
    resultado = parsear_recibo(texto)
    return resultado
