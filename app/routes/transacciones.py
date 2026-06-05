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
    """Registro rápido: pegar recibo → confirmar datos → guardar."""
    from app.utils.parse_recibo import parsear_recibo
    from datetime import date
    
    servicios = Servicio.query.filter_by(activo=True).all()
    paso = request.args.get('paso', '1')
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'analizar':
            # Paso 2: analizar texto del recibo
            texto_recibo = request.form.get('texto_recibo', '')
            datos = parsear_recibo(texto_recibo)
            
            # Buscar cliente por documento exacto
            cliente = None
            if datos.get('documento'):
                cliente = Cliente.query.filter(
                    Cliente.documento.ilike(datos['documento'])
                ).first()
            
            # Buscar candidatos por nombre/apellido/teléfono (evitar duplicados)
            candidatos = []
            if not cliente:
                query = Cliente.query
                filtros = []
                if datos.get('nombre'):
                    filtros.append(Cliente.nombre.ilike(f"%{datos['nombre']}%"))
                if datos.get('apellido'):
                    filtros.append(Cliente.apellido.ilike(f"%{datos['apellido']}%"))
                if datos.get('telefono'):
                    tel_limpio = re.sub(r'[^\d]', '', datos['telefono'])
                    if len(tel_limpio) >= 7:
                        filtros.append(Cliente.telefono.ilike(f"%{tel_limpio}%"))
                
                if filtros:
                    from sqlalchemy import or_
                    candidatos = query.filter(or_(*filtros)).limit(5).all()
            
            return render_template('transacciones/registro_rapido.html',
                                   paso='2',
                                   datos=datos,
                                   cliente=cliente,
                                   candidatos=candidatos,
                                   servicios=servicios,
                                   texto_recibo=texto_recibo)
        
        elif action == 'confirmar':
            # Paso 3: guardar transacción
            cliente_id = request.form.get('cliente_id', type=int)
            documento = request.form.get('documento', '').strip()
            nombre = request.form.get('nombre', '').strip()
            apellido = request.form.get('apellido', '').strip()
            telefono = request.form.get('telefono', '').strip()
            fecha_nacimiento_str = request.form.get('fecha_nacimiento', '').strip()
            servicio_id = request.form.get('servicio_id', type=int)
            monto_str = request.form.get('monto', '').strip()
            
            # Validar servicio
            servicio = Servicio.query.get(servicio_id) if servicio_id else None
            if not servicio:
                flash('Debes seleccionar un servicio', 'danger')
                return redirect(url_for('transacciones.registro_rapido'))
            
            # Parsear monto
            try:
                monto = float(monto_str.replace(',', '.'))
            except ValueError:
                flash('El monto no es válido', 'danger')
                return redirect(url_for('transacciones.registro_rapido'))
            
            # Buscar o crear cliente
            cliente = None
            if cliente_id:
                cliente = Cliente.query.get(cliente_id)
            
            if not cliente and documento:
                cliente = Cliente.query.filter(
                    Cliente.documento.ilike(documento)
                ).first()
            
            if not cliente:
                # Crear cliente nuevo
                if not nombre or not apellido or not documento:
                    flash('Faltan datos del cliente (nombre, apellido, documento)', 'danger')
                    return redirect(url_for('transacciones.registro_rapido'))
                
                # Fecha de nacimiento
                fecha_nacimiento = date(1990, 1, 1)
                if fecha_nacimiento_str:
                    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
                        try:
                            fecha_nacimiento = datetime.strptime(fecha_nacimiento_str, fmt).date()
                            break
                        except ValueError:
                            continue
                
                cliente = Cliente(
                    nombre=nombre,
                    apellido=apellido,
                    documento=documento,
                    telefono=telefono or None,
                    fecha_nacimiento=fecha_nacimiento,
                    ultima_visita=datetime.utcnow()
                )
                db.session.add(cliente)
                db.session.flush()
                
                cliente.servicios.append(servicio)
            else:
                cliente.ultima_visita = datetime.utcnow()
                if servicio not in cliente.servicios:
                    cliente.servicios.append(servicio)
            
            # PREVENCIÓN DE DUPLICADOS
            # Verificar si ya existe una transacción similar en las últimas 24h
            desde = datetime.utcnow() - timedelta(hours=24)
            dup = Transaccion.query.filter(
                Transaccion.cliente_id == cliente.id,
                Transaccion.servicio_id == servicio.id,
                Transaccion.monto == monto,
                Transaccion.fecha >= desde
            ).first()
            
            if dup:
                flash(
                    f'⚠️ Parece que esta transacción ya fue registrada hace '
                    f'{int((datetime.utcnow() - dup.fecha).total_seconds() // 60)} minutos '
                    f'({cliente.nombre_completo()} - {monto:.2f}€). '
                    f'Si estás seguro de que es una transacción distinta, podés continuar desde '
                    f'<a href="{url_for("transacciones.nueva", cliente_id=cliente.id)}">acá</a>.',
                    'warning'
                )
                return redirect(url_for('transacciones.registro_rapido'))
            
            # Crear transacción
            comision = round(monto * (servicio.comision_porcentaje or 0) / 100, 2)
            transaccion = Transaccion(
                cliente_id=cliente.id,
                servicio_id=servicio.id,
                monto=monto,
                comision=comision,
                creado_por=current_user.id
            )
            db.session.add(transaccion)
            db.session.commit()
            
            flash(f'Transacción registrada: {cliente.nombre_completo()} - {monto:.2f}€ ({servicio.nombre})', 'success')
            return redirect(url_for('transacciones.registro_rapido'))
    
    # GET: mostrar paso 1
    return render_template('transacciones/registro_rapido.html',
                           paso='1',
                           servicios=servicios)
