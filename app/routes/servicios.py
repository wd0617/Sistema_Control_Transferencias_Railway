from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.decorators import admin_required
from app.models.cliente import Servicio
from app import db
from datetime import datetime

servicios = Blueprint('servicios', __name__)

@servicios.route('/')
@login_required
def lista():
    servicios_list = Servicio.query.all()
    return render_template('servicios/lista.html', servicios=servicios_list, now=datetime.now())

@servicios.route('/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def nuevo():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        comision = request.form.get('comision')
        
        if not nombre or not comision:
            flash('Todos los campos son obligatorios', 'danger')
            return redirect(url_for('servicios.nuevo'))
        
        try:
            comision = float(comision)
        except ValueError:
            flash('La comisión debe ser un valor numérico', 'danger')
            return redirect(url_for('servicios.nuevo'))
        
        nuevo_servicio = Servicio(
            nombre=nombre,
            comision_porcentaje=comision
        )
        
        db.session.add(nuevo_servicio)
        db.session.commit()
        
        flash('Servicio agregado correctamente', 'success')
        return redirect(url_for('servicios.lista'))
    
    return render_template('servicios/nuevo.html', now=datetime.now())

@servicios.route('/editar/<int:servicio_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar(servicio_id):
    servicio = Servicio.query.get_or_404(servicio_id)
    
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        comision = request.form.get('comision')
        
        if not nombre or not comision:
            flash('Todos los campos son obligatorios', 'danger')
            return redirect(url_for('servicios.editar', servicio_id=servicio_id))
        
        try:
            comision = float(comision)
        except ValueError:
            flash('La comisión debe ser un valor numérico', 'danger')
            return redirect(url_for('servicios.editar', servicio_id=servicio_id))
        
        servicio.nombre = nombre
        servicio.comision_porcentaje = comision
        
        db.session.commit()
        
        flash('Servicio actualizado correctamente', 'success')
        return redirect(url_for('servicios.lista'))
    
    return render_template('servicios/editar.html', servicio=servicio, now=datetime.now())

@servicios.route('/eliminar/<int:servicio_id>', methods=['POST'])
@login_required
@admin_required
def eliminar(servicio_id):
    servicio = Servicio.query.get_or_404(servicio_id)
    
    # Soft delete: marcar como inactivo en lugar de borrar físicamente
    # Esto preserva el historial de transacciones asociadas
    servicio.activo = False
    db.session.commit()
    
    flash('Servicio desactivado correctamente', 'success')
    return redirect(url_for('servicios.lista'))
