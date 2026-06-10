from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from datetime import datetime, timedelta
from app.models.cliente import Cliente, Servicio
from app.models.transaccion import Transaccion
from app import db

clientes = Blueprint('clientes', __name__)

@clientes.route('/')
@login_required
def lista():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    pagination = Cliente.query.order_by(Cliente.ultima_visita.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template('clientes/lista.html', clientes=pagination.items, pagination=pagination, now=datetime.now())

@clientes.route('/search')
@login_required
def search():
    query = request.args.get('q', '').strip()
    clientes_list = []
    saldos = {}
    
    try:
        if query:
            # Búsqueda por nombre, apellido, documento o teléfono
            # Precargar servicios para evitar N+1 queries
            clientes_list = Cliente.query.options(
                joinedload(Cliente.servicios)
            ).filter(
                (Cliente.nombre.ilike(f'%{query}%')) | 
                (Cliente.apellido.ilike(f'%{query}%')) | 
                (Cliente.documento.ilike(f'%{query}%')) |
                (Cliente.telefono.ilike(f'%{query}%'))
            ).all()
            
            # Precalcular saldos semanales en una sola query (evita N+1)
            if clientes_list:
                cliente_ids = [c.id for c in clientes_list]
                fecha_inicio = datetime.utcnow() - timedelta(days=7)
                
                resultados = db.session.query(
                    Transaccion.cliente_id,
                    func.sum(Transaccion.monto).label('total')
                ).filter(
                    Transaccion.cliente_id.in_(cliente_ids),
                    Transaccion.fecha >= fecha_inicio
                ).group_by(Transaccion.cliente_id).all()
                
                # Convertir a diccionario {cliente_id: saldo_disponible}
                sumas = {r.cliente_id: float(r.total or 0) for r in resultados}
                limite = current_app.config.get('LIMITE_TRANSFERENCIA_SEMANAL', 999)
                saldos = {cid: limite - sumas.get(cid, 0) for cid in cliente_ids}
    except Exception as e:
        current_app.logger.error(f'Error en búsqueda de clientes: {e}', exc_info=True)
        flash('Ocurrió un error al realizar la búsqueda. Inténtalo de nuevo.', 'danger')
        return render_template('clientes/search_results.html', clientes=[], query=query, saldos={}, now=datetime.now())
    
    return render_template('clientes/search_results.html', clientes=clientes_list, query=query, saldos=saldos, now=datetime.now())

@clientes.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    if request.method == 'POST':
        # Recoger datos del formulario
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        documento = request.form.get('documento')
        telefono = request.form.get('telefono')
        fecha_nacimiento = request.form.get('fecha_nacimiento')
        
        # Nuevos campos de documento
        tipo_documento = request.form.get('tipo_documento', 'NIE')
        documento_fecha_emision = request.form.get('documento_fecha_emision')
        documento_fecha_vencimiento = request.form.get('documento_fecha_vencimiento')
        
        # Para evitar errores, ignoramos los campos que no existen en el modelo
        # (nacionalidad, email, direccion, notas)
        
        # Convertir fecha de nacimiento
        fecha_nacimiento_obj = None
        if fecha_nacimiento:
            try:
                fecha_nacimiento_obj = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
            except ValueError:
                flash('Formato de fecha incorrecto', 'danger')
                return redirect(url_for('clientes.nuevo'))
        else:
            flash('La fecha de nacimiento es obligatoria', 'danger')
            return redirect(url_for('clientes.nuevo'))

        # Convertir fechas del documento
        doc_emision_obj = None
        if documento_fecha_emision:
            try:
                doc_emision_obj = datetime.strptime(documento_fecha_emision, '%Y-%m-%d').date()
            except ValueError:
                pass

        doc_vencimiento_obj = None
        if documento_fecha_vencimiento:
            try:
                doc_vencimiento_obj = datetime.strptime(documento_fecha_vencimiento, '%Y-%m-%d').date()
            except ValueError:
                pass

        # Usar helper que evita duplicados y gestiona documentos
        from app.utils.cliente_utils import obtener_o_crear_cliente_con_documento
        cliente, es_nuevo = obtener_o_crear_cliente_con_documento(
            nombre=nombre,
            apellido=apellido,
            documento=documento,
            telefono=telefono,
            tipo_documento=tipo_documento,
            fecha_nacimiento=fecha_nacimiento_obj,
            doc_fecha_emision=doc_emision_obj,
            doc_fecha_vencimiento=doc_vencimiento_obj
        )

        if not es_nuevo:
            db.session.commit()
            flash('El cliente ya existía. Se actualizaron los datos del documento.', 'info')
            return redirect(url_for('clientes.editar', cliente_id=cliente.id))

        # Agregar servicios al cliente nuevo
        servicios_ids = request.form.getlist('servicios')
        for servicio_id in servicios_ids:
            servicio = Servicio.query.get(servicio_id)
            if servicio:
                cliente.servicios.append(servicio)

        db.session.commit()
        flash('Cliente registrado correctamente', 'success')
        return redirect(url_for('clientes.lista'))
    
    # GET: Mostrar formulario
    servicios = Servicio.query.all()
    return render_template('clientes/nuevo.html', servicios=servicios, now=datetime.now())

@clientes.route('/editar/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def editar(cliente_id):
    # Obtener el cliente
    cliente = Cliente.query.get_or_404(cliente_id)
    
    if request.method == 'POST':
        # Recoger datos del formulario
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        documento = request.form.get('documento')
        telefono = request.form.get('telefono')
        fecha_nacimiento = request.form.get('fecha_nacimiento')
        
        # Nuevos campos de documento
        tipo_documento = request.form.get('tipo_documento', 'NIE')
        documento_fecha_emision = request.form.get('documento_fecha_emision')
        documento_fecha_vencimiento = request.form.get('documento_fecha_vencimiento')
        
        # Verificar si se está intentando cambiar el documento a uno ya existente
        if documento != cliente.documento:
            cliente_existente = Cliente.query.filter_by(documento=documento).first()
            if cliente_existente:
                flash('Ya existe un cliente con ese documento', 'danger')
                return redirect(url_for('clientes.editar', cliente_id=cliente.id))
        
        # Convertir fecha de nacimiento
        fecha_nacimiento_obj = None
        if fecha_nacimiento:
            try:
                fecha_nacimiento_obj = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
            except ValueError:
                flash('Formato de fecha incorrecto', 'danger')
                return redirect(url_for('clientes.editar', cliente_id=cliente.id))
        else:
            flash('La fecha de nacimiento es obligatoria', 'danger')
            return redirect(url_for('clientes.editar', cliente_id=cliente.id))
        
        # Convertir fechas del documento
        doc_emision_obj = None
        if documento_fecha_emision:
            try:
                doc_emision_obj = datetime.strptime(documento_fecha_emision, '%Y-%m-%d').date()
            except ValueError:
                pass  # Ignorar si no tiene formato correcto
        
        doc_vencimiento_obj = None
        if documento_fecha_vencimiento:
            try:
                doc_vencimiento_obj = datetime.strptime(documento_fecha_vencimiento, '%Y-%m-%d').date()
            except ValueError:
                pass  # Ignorar si no tiene formato correcto
        
        # Actualizar datos del cliente
        cliente.nombre = nombre
        cliente.apellido = apellido
        cliente.documento = documento
        cliente.telefono = telefono
        cliente.fecha_nacimiento = fecha_nacimiento_obj
        cliente.ultima_visita = datetime.now()
        
        # Actualizar campos de documento
        cliente.tipo_documento = tipo_documento
        cliente.documento_fecha_emision = doc_emision_obj
        cliente.documento_fecha_vencimiento = doc_vencimiento_obj
        
        # Actualizar servicios del cliente (primero eliminar todos y luego agregar los seleccionados)
        cliente.servicios = []  # Eliminar relaciones existentes
        
        servicios_ids = request.form.getlist('servicios')
        for servicio_id in servicios_ids:
            servicio = Servicio.query.get(servicio_id)
            if servicio:
                cliente.servicios.append(servicio)
        
        db.session.commit()
        flash('Cliente actualizado correctamente', 'success')
        return redirect(url_for('clientes.lista'))
    
    # GET: Mostrar formulario con datos del cliente
    servicios = Servicio.query.all()
    return render_template('clientes/editar.html', cliente=cliente, servicios=servicios, now=datetime.now())
