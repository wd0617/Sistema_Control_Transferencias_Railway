from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from datetime import datetime, timedelta
from app.models.cliente import Cliente, Servicio
from app.models.transaccion import Transaccion
from app import db
from app.utils.tenancy import query_negocio, get_negocio_o_404, current_negocio_id

clientes = Blueprint('clientes', __name__)

@clientes.route('/')
@login_required
def lista():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    pagination = query_negocio(Cliente).order_by(Cliente.ultima_visita.desc()).paginate(
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
            # Búsqueda por nombre, apellido, documento (principal y secundarios) o teléfono
            from app.models.documento import DocumentoCliente
            doc_cliente_ids = query_negocio(DocumentoCliente).filter(
                DocumentoCliente.numero_documento.ilike(f'%{query}%')
            ).with_entities(DocumentoCliente.cliente_id).subquery()

            # Precargar servicios para evitar N+1 queries
            clientes_list = query_negocio(Cliente).options(
                joinedload(Cliente.servicios)
            ).filter(
                (Cliente.nombre.ilike(f'%{query}%')) | 
                (Cliente.apellido.ilike(f'%{query}%')) | 
                (Cliente.documento.ilike(f'%{query}%')) |
                (Cliente.id.in_(doc_cliente_ids)) |
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
            servicio = query_negocio(Servicio).filter_by(id=servicio_id).first()
            if servicio:
                cliente.servicios.append(servicio)

        db.session.commit()
        flash('Cliente registrado correctamente', 'success')
        return redirect(url_for('clientes.lista'))
    
    # GET: Mostrar formulario
    servicios = query_negocio(Servicio).all()
    return render_template('clientes/nuevo.html', servicios=servicios, now=datetime.now())

@clientes.route('/editar/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def editar(cliente_id):
    # Obtener el cliente
    cliente = get_negocio_o_404(Cliente, cliente_id)
    
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
            cliente_existente = query_negocio(Cliente).filter_by(documento=documento).first()
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
            servicio = query_negocio(Servicio).filter_by(id=servicio_id).first()
            if servicio:
                cliente.servicios.append(servicio)
        
        db.session.commit()
        flash('Cliente actualizado correctamente', 'success')
        return redirect(url_for('clientes.lista'))
    
    # GET: Mostrar formulario con datos del cliente
    servicios = query_negocio(Servicio).all()
    return render_template('clientes/editar.html', cliente=cliente, servicios=servicios, now=datetime.now())


@clientes.route('/<int:cliente_id>/documentos/agregar', methods=['POST'])
@login_required
def agregar_documento(cliente_id):
    """Vincula un nuevo documento de identidad al cliente."""
    cliente = get_negocio_o_404(Cliente, cliente_id)
    tipo = request.form.get('tipo_documento', 'OTRO').strip().upper()
    numero = request.form.get('numero_documento', '').strip().upper()
    fecha_emision_str = request.form.get('fecha_emision')
    fecha_vencimiento_str = request.form.get('fecha_vencimiento')
    
    if not numero:
        flash('El número de documento es obligatorio.', 'danger')
        return redirect(url_for('clientes.editar', cliente_id=cliente.id))
        
    # Validar si ya es el documento principal de este cliente
    if cliente.documento and cliente.documento.strip().upper() == numero:
        flash('Este número ya es el documento principal del cliente.', 'warning')
        return redirect(url_for('clientes.editar', cliente_id=cliente.id))
        
    # Validar si ya existe en DocumentoCliente para este cliente
    from app.models.documento import DocumentoCliente
    doc_existente = query_negocio(DocumentoCliente).filter_by(
        cliente_id=cliente.id,
        numero_documento=numero
    ).first()
    if doc_existente:
        flash('Este documento ya está registrado para este cliente.', 'warning')
        return redirect(url_for('clientes.editar', cliente_id=cliente.id))
        
    # Convertir fechas
    fecha_emision = None
    if fecha_emision_str:
        try:
            fecha_emision = datetime.strptime(fecha_emision_str, '%Y-%m-%d').date()
        except ValueError:
            pass
            
    fecha_vencimiento = None
    if fecha_vencimiento_str:
        try:
            fecha_vencimiento = datetime.strptime(fecha_vencimiento_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if not fecha_vencimiento:
        from datetime import date
        fecha_vencimiento = date(2099, 12, 31)
        
    from app.utils.cliente_utils import _crear_documento_cliente
    _crear_documento_cliente(cliente, numero, tipo, fecha_emision, fecha_vencimiento)
    db.session.commit()
    flash(f'Documento {tipo} ({numero}) vinculado correctamente.', 'success')
    return redirect(url_for('clientes.editar', cliente_id=cliente.id))


@clientes.route('/<int:cliente_id>/documentos/<int:doc_id>/hacer-principal', methods=['POST'])
@login_required
def hacer_documento_principal(cliente_id, doc_id):
    """Convierte un documento secundario en el documento principal del cliente."""
    cliente = get_negocio_o_404(Cliente, cliente_id)
    from app.models.documento import DocumentoCliente
    doc = get_negocio_o_404(DocumentoCliente, doc_id)
    
    if doc.cliente_id != cliente.id:
        flash('El documento no pertenece a este cliente.', 'danger')
        return redirect(url_for('clientes.editar', cliente_id=cliente.id))
        
    # Guardar documento principal actual en DocumentoCliente (si no está)
    from app.utils.cliente_utils import _crear_documento_cliente
    if cliente.documento:
        _crear_documento_cliente(
            cliente=cliente,
            numero=cliente.documento,
            tipo=cliente.tipo_documento,
            fecha_emision=cliente.documento_fecha_emision,
            fecha_vencimiento=cliente.documento_fecha_vencimiento
        )
        
    # Promover este documento a principal
    cliente.documento = doc.numero_documento
    cliente.tipo_documento = doc.tipo_documento
    cliente.documento_fecha_emision = doc.fecha_emision
    cliente.documento_fecha_vencimiento = doc.fecha_vencimiento
    
    # Eliminar el registro de DocumentoCliente ya que ahora es el principal
    db.session.delete(doc)
    db.session.commit()
    
    flash(f'El documento {cliente.tipo_documento} ({cliente.documento}) es ahora el principal.', 'success')
    return redirect(url_for('clientes.editar', cliente_id=cliente.id))


@clientes.route('/<int:cliente_id>/documentos/<int:doc_id>/eliminar', methods=['POST'])
@login_required
def eliminar_documento_secundario(cliente_id, doc_id):
    """Elimina un documento secundario de un cliente."""
    cliente = get_negocio_o_404(Cliente, cliente_id)
    from app.models.documento import DocumentoCliente
    doc = get_negocio_o_404(DocumentoCliente, doc_id)
    
    if doc.cliente_id != cliente.id:
        flash('El documento no pertenece a este cliente.', 'danger')
        return redirect(url_for('clientes.editar', cliente_id=cliente.id))
        
    numero = doc.numero_documento
    db.session.delete(doc)
    db.session.commit()
    
    flash(f'Documento {numero} desvinculado correctamente.', 'info')
    return redirect(url_for('clientes.editar', cliente_id=cliente.id))


@clientes.route('/unificar', methods=['GET', 'POST'])
@login_required
def unificar():
    """Herramienta para detectar y fusionar clientes duplicados en un único perfil."""
    from app.utils.cliente_utils import (
        analizar_duplicados_negocio,
        ejecutar_unificacion_automatica,
        fusionar_clientes
    )
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        
        # 1. Unificación automática de alta certeza (nombre + apellido + teléfono + fecha nacimiento)
        if accion == 'auto_unificar':
            try:
                resumen = ejecutar_unificacion_automatica(negocio_id=current_negocio_id(), user_id=current_user.id)
                if resumen['clientes_fusionados'] > 0:
                    flash(
                        f"¡Unificación automática completada con éxito! Se procesaron {resumen['grupos_procesados']} grupo(s) "
                        f"y se fusionaron {resumen['clientes_fusionados']} perfil(es) duplicado(s) de forma segura.",
                        'success'
                    )
                else:
                    flash("No se encontraron clientes duplicados con coincidencia exacta de nombre, teléfono y fecha de nacimiento.", 'info')
                return redirect(url_for('clientes.unificar'))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f'Error en unificación automática: {e}', exc_info=True)
                flash(f'Ocurrió un error en la unificación automática: {str(e)}', 'danger')
                return redirect(url_for('clientes.unificar'))

        # 2. Unificación manual de dos clientes específicos
        maestro_id = request.form.get('cliente_maestro_id', type=int)
        duplicado_id = request.form.get('cliente_duplicado_id', type=int)
        
        if not maestro_id or not duplicado_id:
            flash('Debes seleccionar tanto el cliente principal como el duplicado.', 'danger')
            return redirect(url_for('clientes.unificar'))
            
        if maestro_id == duplicado_id:
            flash('No puedes seleccionar el mismo cliente como principal y duplicado.', 'warning')
            return redirect(url_for('clientes.unificar'))
            
        cliente_maestro = get_negocio_o_404(Cliente, maestro_id)
        cliente_duplicado = get_negocio_o_404(Cliente, duplicado_id)
        
        try:
            fusionar_clientes(cliente_maestro, cliente_duplicado, user_id=current_user.id)
            flash(f'¡Perfiles unificados con éxito! Todas las transacciones y documentos fueron consolidados en {cliente_maestro.nombre_completo()}.', 'success')
            return redirect(url_for('clientes.editar', cliente_id=cliente_maestro.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error al fusionar clientes: {e}', exc_info=True)
            flash(f'Ocurrió un error al unificar clientes: {str(e)}', 'danger')
            return redirect(url_for('clientes.unificar'))
            
    # GET: Analizar duplicados (automáticos de alta certeza vs manuales)
    analisis = analizar_duplicados_negocio(negocio_id=current_negocio_id())
    duplicados_automaticos = analisis['automaticos']
    duplicados_manuales = analisis['manuales']
    
    # Obtener lista completa de clientes para los selectores manuales
    todos_clientes = query_negocio(Cliente).order_by(Cliente.nombre, Cliente.apellido).all()

    # Si vienen IDs por query params (ej. para preseleccionar desde lista)
    c1_id = request.args.get('c1', type=int)
    c2_id = request.args.get('c2', type=int)
    c1 = get_negocio_o_404(Cliente, c1_id) if c1_id else None
    c2 = get_negocio_o_404(Cliente, c2_id) if c2_id else None
    
    return render_template('clientes/unificar.html',
                           duplicados_automaticos=duplicados_automaticos,
                           duplicados_manuales=duplicados_manuales,
                           grupos_duplicados=duplicados_manuales,
                           todos_clientes=todos_clientes,
                           c1=c1,
                           c2=c2,
                           now=datetime.now())

