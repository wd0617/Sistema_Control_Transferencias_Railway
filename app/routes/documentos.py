import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.decorators import admin_required
from app.models.cliente import Cliente
from app.models.documento import DocumentoCliente
from app.extensions import db
from datetime import datetime, date, timedelta

documentos = Blueprint('documentos', __name__)

def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida."""
    ALLOWED_EXTENSIONS = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'pdf'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file, subfolder='documentos'):
    """Guarda un archivo subido y retorna la ruta relativa."""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Añadir timestamp para evitar colisiones
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        # Crear directorio si no existe
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
        os.makedirs(upload_path, exist_ok=True)
        
        filepath = os.path.join(upload_path, filename)
        file.save(filepath)
        
        # Retornar ruta relativa para guardar en BD
        return os.path.join(subfolder, filename)
    return None


@documentos.route('/')
@login_required
def lista():
    """Lista todos los documentos con filtros por estado."""
    estado = request.args.get('estado', 'todos')
    dias_alerta = current_app.config.get('DIAS_ALERTA_VENCIMIENTO', 30)
    
    if estado == 'vencidos':
        docs = DocumentoCliente.obtener_documentos_vencidos()
        titulo = 'Documentos Vencidos'
    elif estado == 'por_vencer':
        docs = DocumentoCliente.obtener_documentos_por_vencer(dias_alerta)
        titulo = f'Documentos por Vencer (próximos {dias_alerta} días)'
    else:
        docs = DocumentoCliente.query.order_by(DocumentoCliente.fecha_vencimiento).all()
        titulo = 'Todos los Documentos'
    
    # Actualizar estados
    for doc in docs:
        doc.actualizar_estado(dias_alerta)
    
    # Obtener estadísticas
    stats = DocumentoCliente.contar_por_estado()
    
    return render_template('documentos/lista.html', 
                          documentos=docs,
                          titulo=titulo,
                          estado_actual=estado,
                          stats=stats,
                          now=datetime.now())


@documentos.route('/cliente/<int:cliente_id>')
@login_required
def documentos_cliente(cliente_id):
    """Muestra los documentos de un cliente específico."""
    cliente = Cliente.query.get_or_404(cliente_id)
    docs = DocumentoCliente.query.filter_by(cliente_id=cliente_id).order_by(
        DocumentoCliente.es_documento_principal.desc(),
        DocumentoCliente.fecha_vencimiento
    ).all()
    
    # Actualizar estados
    dias_alerta = current_app.config.get('DIAS_ALERTA_VENCIMIENTO', 30)
    for doc in docs:
        doc.actualizar_estado(dias_alerta)
    
    return render_template('documentos/cliente_documentos.html',
                          cliente=cliente,
                          documentos=docs,
                          now=datetime.now())


@documentos.route('/nuevo/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def nuevo(cliente_id):
    """Registra un nuevo documento para un cliente."""
    cliente = Cliente.query.get_or_404(cliente_id)
    
    if request.method == 'POST':
        tipo_documento = request.form.get('tipo_documento')
        numero_documento = request.form.get('numero_documento')
        pais_emision = request.form.get('pais_emision', 'España')
        fecha_emision = request.form.get('fecha_emision')
        fecha_vencimiento = request.form.get('fecha_vencimiento')
        es_principal = request.form.get('es_documento_principal') == 'on'
        notas = request.form.get('notas')
        
        # Validaciones
        if not tipo_documento or not numero_documento or not fecha_vencimiento:
            flash('Los campos Tipo, Número y Fecha de Vencimiento son obligatorios', 'danger')
            return redirect(url_for('documentos.nuevo', cliente_id=cliente_id))
        
        # Convertir fechas
        try:
            fecha_vencimiento_obj = datetime.strptime(fecha_vencimiento, '%Y-%m-%d').date()
            fecha_emision_obj = datetime.strptime(fecha_emision, '%Y-%m-%d').date() if fecha_emision else None
        except ValueError:
            flash('Formato de fecha incorrecto', 'danger')
            return redirect(url_for('documentos.nuevo', cliente_id=cliente_id))
        
        # Procesar archivos subidos
        foto_anverso = None
        foto_reverso = None
        
        if 'foto_anverso' in request.files:
            file = request.files['foto_anverso']
            if file.filename:
                foto_anverso = save_uploaded_file(file, f'documentos/{cliente_id}')
        
        if 'foto_reverso' in request.files:
            file = request.files['foto_reverso']
            if file.filename:
                foto_reverso = save_uploaded_file(file, f'documentos/{cliente_id}')
        
        # Si es documento principal, quitar el flag de otros documentos
        if es_principal:
            DocumentoCliente.query.filter_by(
                cliente_id=cliente_id, 
                es_documento_principal=True
            ).update({'es_documento_principal': False})
        
        # Crear documento
        nuevo_doc = DocumentoCliente(
            cliente_id=cliente_id,
            tipo_documento=tipo_documento,
            numero_documento=numero_documento,
            pais_emision=pais_emision,
            fecha_emision=fecha_emision_obj,
            fecha_vencimiento=fecha_vencimiento_obj,
            foto_anverso=foto_anverso,
            foto_reverso=foto_reverso,
            es_documento_principal=es_principal,
            notas=notas,
            actualizado_por=current_user.id
        )
        
        # Actualizar estado basado en vencimiento
        dias_alerta = current_app.config.get('DIAS_ALERTA_VENCIMIENTO', 30)
        nuevo_doc.actualizar_estado(dias_alerta)
        
        db.session.add(nuevo_doc)
        db.session.commit()
        
        flash('Documento registrado correctamente', 'success')
        return redirect(url_for('documentos.documentos_cliente', cliente_id=cliente_id))
    
    # GET: Mostrar formulario
    return render_template('documentos/nuevo.html',
                          cliente=cliente,
                          tipos_documento=DocumentoCliente.TIPOS_DOCUMENTO,
                          now=datetime.now())


@documentos.route('/editar/<int:documento_id>', methods=['GET', 'POST'])
@login_required
def editar(documento_id):
    """Edita un documento existente."""
    doc = DocumentoCliente.query.get_or_404(documento_id)
    cliente = doc.cliente
    
    if request.method == 'POST':
        # Actualizar campos
        doc.tipo_documento = request.form.get('tipo_documento')
        doc.numero_documento = request.form.get('numero_documento')
        doc.pais_emision = request.form.get('pais_emision', 'España')
        doc.notas = request.form.get('notas')
        
        # Fechas
        fecha_emision = request.form.get('fecha_emision')
        fecha_vencimiento = request.form.get('fecha_vencimiento')
        
        try:
            if fecha_vencimiento:
                doc.fecha_vencimiento = datetime.strptime(fecha_vencimiento, '%Y-%m-%d').date()
            if fecha_emision:
                doc.fecha_emision = datetime.strptime(fecha_emision, '%Y-%m-%d').date()
        except ValueError:
            flash('Formato de fecha incorrecto', 'danger')
            return redirect(url_for('documentos.editar', documento_id=documento_id))
        
        # Documento principal
        es_principal = request.form.get('es_documento_principal') == 'on'
        if es_principal and not doc.es_documento_principal:
            DocumentoCliente.query.filter_by(
                cliente_id=doc.cliente_id, 
                es_documento_principal=True
            ).update({'es_documento_principal': False})
        doc.es_documento_principal = es_principal
        
        # Procesar nuevos archivos si se suben
        if 'foto_anverso' in request.files:
            file = request.files['foto_anverso']
            if file.filename:
                new_path = save_uploaded_file(file, f'documentos/{doc.cliente_id}')
                if new_path:
                    doc.foto_anverso = new_path
        
        if 'foto_reverso' in request.files:
            file = request.files['foto_reverso']
            if file.filename:
                new_path = save_uploaded_file(file, f'documentos/{doc.cliente_id}')
                if new_path:
                    doc.foto_reverso = new_path
        
        # Actualizar estado y auditoría
        dias_alerta = current_app.config.get('DIAS_ALERTA_VENCIMIENTO', 30)
        doc.actualizar_estado(dias_alerta)
        doc.actualizado_por = current_user.id
        
        db.session.commit()
        
        flash('Documento actualizado correctamente', 'success')
        return redirect(url_for('documentos.documentos_cliente', cliente_id=doc.cliente_id))
    
    # GET: Mostrar formulario
    return render_template('documentos/editar.html',
                          documento=doc,
                          cliente=cliente,
                          tipos_documento=DocumentoCliente.TIPOS_DOCUMENTO,
                          now=datetime.now())


@documentos.route('/eliminar/<int:documento_id>', methods=['POST'])
@login_required
@admin_required
def eliminar(documento_id):
    """Elimina un documento."""
    doc = DocumentoCliente.query.get_or_404(documento_id)
    cliente_id = doc.cliente_id
    
    db.session.delete(doc)
    db.session.commit()
    
    flash('Documento eliminado correctamente', 'success')
    return redirect(url_for('documentos.documentos_cliente', cliente_id=cliente_id))


@documentos.route('/alertas')
@login_required
def alertas():
    """Muestra alertas de documentos que requieren atención."""
    dias_alerta = current_app.config.get('DIAS_ALERTA_VENCIMIENTO', 30)
    
    vencidos = DocumentoCliente.obtener_documentos_vencidos()
    por_vencer = DocumentoCliente.obtener_documentos_por_vencer(dias_alerta)
    
    return render_template('documentos/alertas.html',
                          vencidos=vencidos,
                          por_vencer=por_vencer,
                          dias_alerta=dias_alerta,
                          now=datetime.now())
