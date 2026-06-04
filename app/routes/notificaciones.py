from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_required
from app.extensions import db
from app.models.transaccion import Notificacion
from app.utils.notificaciones import contar_notificaciones_pendientes, obtener_notificaciones_pendientes
import traceback

notificaciones = Blueprint('notificaciones', __name__)

@notificaciones.route('/')
@login_required
def lista():
    """Muestra todas las notificaciones pendientes."""
    try:
        notifs = Notificacion.query.filter_by(leida=False).order_by(
            Notificacion.fecha_creacion.desc()
        ).all()
        return render_template('notificaciones/lista.html', notificaciones=notifs)
    except Exception as e:
        current_app.logger.error('Error en notificaciones.lista: %s', traceback.format_exc())
        flash('No se pudieron cargar las notificaciones. El sistema las generará automáticamente.', 'warning')
        return render_template('notificaciones/lista.html', notificaciones=[])

@notificaciones.route('/marcar-leida/<int:notificacion_id>')
@login_required
def marcar_leida(notificacion_id):
    """Marca una notificación como leída."""
    notif = Notificacion.query.get_or_404(notificacion_id)
    notif.leida = True
    notif.fecha_lectura = db.func.now()
    db.session.commit()
    flash('Notificación marcada como leída', 'success')
    return redirect(url_for('notificaciones.lista'))

@notificaciones.route('/marcar-todas-leidas')
@login_required
def marcar_todas_leidas():
    """Marca todas las notificaciones como leídas."""
    Notificacion.query.filter_by(leida=False).update({
        'leida': True,
        'fecha_lectura': db.func.now()
    })
    db.session.commit()
    flash('Todas las notificaciones han sido marcadas como leídas', 'success')
    return redirect(url_for('notificaciones.lista'))
