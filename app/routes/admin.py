"""Panel de administración de la plataforma.

- Superadmin (/admin/negocios...): aprueba/rechaza/suspende negocios,
  ve sus fichas, edita notas internas y entra en "modo soporte" para
  navegar la app como ese negocio.
- Admin de negocio (/admin/usuarios...): gestiona los usuarios de su
  propio negocio.
"""
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import current_user
from sqlalchemy import func

from app import db
from app.decorators import admin_required, superadmin_required
from app.models.negocio import Negocio
from app.models.user import User, ActivityLog
from app.models.cliente import Cliente, Servicio
from app.models.transaccion import Transaccion
from app.models.producto import Producto
from app.utils.tenancy import current_negocio_id

admin = Blueprint('admin', __name__)

# Servicios semilla que se crean al aprobar un negocio (mismos que init_db.py)
SERVICIOS_SEMILLA = [
    ('Western Union', 'Transferencias internacionales', 3.5),
    ('Mondial', 'Transferencias rápidas', 2.8),
    ('Monty', 'Transferencias digitales', 2.0),
    ('Moneygram', 'Transferencias globales', 3.2),
    ('Ria', 'Transferencias a bajo costo', 2.5),
]


def _registrar_actividad(texto):
    db.session.add(ActivityLog(
        user_id=current_user.id,
        activity=texto,
        ip_address=request.remote_addr,
    ))


def _crear_servicios_semilla(negocio_id):
    for nombre, descripcion, comision in SERVICIOS_SEMILLA:
        db.session.add(Servicio(
            negocio_id=negocio_id,
            nombre=nombre,
            descripcion=descripcion,
            comision_porcentaje=comision,
        ))


# ============================================
# Gestión de negocios (superadmin)
# ============================================

@admin.route('/negocios')
@superadmin_required
def negocios():
    pendientes = Negocio.query.filter_by(estado='pendiente').order_by(Negocio.created_at).all()
    resto = Negocio.query.filter(Negocio.estado != 'pendiente') \
        .order_by(Negocio.estado, Negocio.nombre).all()
    return render_template('admin/negocios.html', pendientes=pendientes, resto=resto,
                           estados=dict(Negocio.ESTADOS))


@admin.route('/negocios/<int:id>')
@superadmin_required
def negocio_detalle(id):
    negocio = Negocio.query.get_or_404(id)
    usuarios = User.query.filter_by(negocio_id=id).order_by(User.username).all()
    stats = {
        'clientes': db.session.query(func.count(Cliente.id)).filter(Cliente.negocio_id == id).scalar(),
        'transacciones': db.session.query(func.count(Transaccion.id)).filter(Transaccion.negocio_id == id).scalar(),
        'productos': db.session.query(func.count(Producto.id)).filter(Producto.negocio_id == id).scalar(),
        'volumen': db.session.query(func.coalesce(func.sum(Transaccion.monto), 0))
                            .filter(Transaccion.negocio_id == id).scalar(),
    }
    return render_template('admin/negocio_detalle.html', negocio=negocio,
                           usuarios=usuarios, stats=stats, estados=dict(Negocio.ESTADOS))


@admin.route('/negocios/<int:id>/notas', methods=['POST'])
@superadmin_required
def negocio_notas(id):
    negocio = Negocio.query.get_or_404(id)
    negocio.notas_admin = request.form.get('notas_admin', '').strip()
    _registrar_actividad(f'Notas actualizadas del negocio {negocio.nombre}')
    db.session.commit()
    flash('Notas guardadas.', 'success')
    return redirect(url_for('admin.negocio_detalle', id=id))


def _cambiar_estado_negocio(id, estado_destino):
    negocio = Negocio.query.get_or_404(id)
    negocio.estado = estado_destino
    if estado_destino == 'aprobado':
        negocio.aprobado_at = datetime.utcnow()
        # Activar los usuarios del negocio y crear servicios semilla si no tiene
        User.query.filter_by(negocio_id=id).update({'activo': True})
        if Servicio.query.filter_by(negocio_id=id).count() == 0:
            _crear_servicios_semilla(id)
    db.session.commit()


@admin.route('/negocios/<int:id>/aprobar', methods=['POST'])
@superadmin_required
def aprobar(id):
    _cambiar_estado_negocio(id, 'aprobado')
    negocio = Negocio.query.get(id)
    _registrar_actividad(f'Negocio aprobado: {negocio.nombre}')
    db.session.commit()
    flash(f'Negocio "{negocio.nombre}" aprobado. Sus usuarios ya pueden entrar.', 'success')
    return redirect(url_for('admin.negocios'))


@admin.route('/negocios/<int:id>/rechazar', methods=['POST'])
@superadmin_required
def rechazar(id):
    _cambiar_estado_negocio(id, 'rechazado')
    negocio = Negocio.query.get(id)
    _registrar_actividad(f'Negocio rechazado: {negocio.nombre}')
    db.session.commit()
    flash(f'Negocio "{negocio.nombre}" rechazado.', 'warning')
    return redirect(url_for('admin.negocios'))


@admin.route('/negocios/<int:id>/suspender', methods=['POST'])
@superadmin_required
def suspender(id):
    _cambiar_estado_negocio(id, 'suspendido')
    negocio = Negocio.query.get(id)
    _registrar_actividad(f'Negocio suspendido: {negocio.nombre}')
    db.session.commit()
    flash(f'Negocio "{negocio.nombre}" suspendido. Sus usuarios no podrán entrar.', 'warning')
    return redirect(url_for('admin.negocios'))


@admin.route('/negocios/<int:id>/reactivar', methods=['POST'])
@superadmin_required
def reactivar(id):
    _cambiar_estado_negocio(id, 'aprobado')
    negocio = Negocio.query.get(id)
    _registrar_actividad(f'Negocio reactivado: {negocio.nombre}')
    db.session.commit()
    flash(f'Negocio "{negocio.nombre}" reactivado.', 'success')
    return redirect(url_for('admin.negocios'))


# ============================================
# Modo soporte: ver la app como un negocio
# ============================================

@admin.route('/negocios/<int:id>/ver', methods=['POST'])
@superadmin_required
def ver_como_negocio(id):
    negocio = Negocio.query.get_or_404(id)
    if not negocio.esta_aprobado:
        flash('Solo puedes ver negocios aprobados.', 'warning')
        return redirect(url_for('admin.negocio_detalle', id=id))
    session['negocio_vista'] = negocio.id
    _registrar_actividad(f'Modo soporte: viendo como {negocio.nombre}')
    db.session.commit()
    flash(f'Estás viendo la plataforma como "{negocio.nombre}".', 'info')
    return redirect(url_for('main.dashboard'))


@admin.route('/salir-vista')
@superadmin_required
def salir_vista():
    session.pop('negocio_vista', None)
    flash('Has salido del modo soporte.', 'info')
    return redirect(url_for('admin.negocios'))


# ============================================
# Usuarios del negocio (admin del negocio)
# ============================================

@admin.route('/usuarios')
@admin_required
def usuarios():
    negocio_id = current_negocio_id()
    if negocio_id is None:
        flash('Selecciona un negocio para gestionar sus usuarios.', 'info')
        return redirect(url_for('admin.negocios'))
    lista = User.query.filter_by(negocio_id=negocio_id).order_by(User.username).all()
    return render_template('admin/usuarios.html', usuarios=lista)


@admin.route('/usuarios/nuevo', methods=['GET', 'POST'])
@admin_required
def usuario_nuevo():
    negocio_id = current_negocio_id()
    if negocio_id is None:
        flash('Selecciona un negocio para gestionar sus usuarios.', 'info')
        return redirect(url_for('admin.negocios'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        nombre = (request.form.get('nombre') or '').strip()
        apellido = (request.form.get('apellido') or '').strip()
        password = request.form.get('password') or ''
        es_admin = request.form.get('is_admin') == 'on'

        errores = []
        if not username or len(username) < 3:
            errores.append('El nombre de usuario debe tener al menos 3 caracteres.')
        if not email or '@' not in email:
            errores.append('Ingresa un email válido.')
        if len(password) < 8:
            errores.append('La contraseña debe tener al menos 8 caracteres.')
        if not errores:
            if User.query.filter_by(username=username).first():
                errores.append('Ese nombre de usuario ya está en uso.')
            if User.query.filter_by(email=email).first():
                errores.append('Ese email ya está registrado.')

        if errores:
            for e in errores:
                flash(e, 'danger')
            return render_template('admin/usuario_form.html', datos=request.form)

        usuario = User(
            negocio_id=negocio_id,
            username=username,
            email=email,
            nombre=nombre,
            apellido=apellido,
            is_admin=es_admin,
            activo=True,
        )
        usuario.set_password(password)
        db.session.add(usuario)
        _registrar_actividad(f'Usuario creado: {username}')
        db.session.commit()
        flash(f'Usuario "{username}" creado correctamente.', 'success')
        return redirect(url_for('admin.usuarios'))

    return render_template('admin/usuario_form.html', datos={})


@admin.route('/usuarios/<int:id>/toggle', methods=['POST'])
@admin_required
def usuario_toggle(id):
    """Activa/desactiva un usuario del propio negocio."""
    negocio_id = current_negocio_id()
    usuario = User.query.get_or_404(id)
    if usuario.negocio_id != negocio_id:
        flash('No puedes gestionar usuarios de otro negocio.', 'danger')
        return redirect(url_for('admin.usuarios'))
    if usuario.id == current_user.id:
        flash('No puedes desactivarte a ti mismo.', 'warning')
        return redirect(url_for('admin.usuarios'))
    usuario.activo = not usuario.activo
    _registrar_actividad(
        f'Usuario {"activado" if usuario.activo else "desactivado"}: {usuario.username}')
    db.session.commit()
    flash(f'Usuario "{usuario.username}" {"activado" if usuario.activo else "desactivado"}.', 'success')
    return redirect(url_for('admin.usuarios'))
