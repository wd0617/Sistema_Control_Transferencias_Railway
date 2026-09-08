"""Solicitud pública de acceso a la plataforma.

Cualquier negocio puede pedir acceso desde /solicitar-acceso, pero solo
entra si el superadmin lo aprueba desde /admin/negocios. El usuario creado
queda inactivo (activo=False) hasta la aprobación.
"""
from flask import Blueprint, render_template, flash, request, redirect, url_for
from flask_login import current_user

from app import db
from app.models.negocio import Negocio
from app.models.user import User
from app.utils.telegram import notificar_telegram

registro = Blueprint('registro', __name__)


@registro.route('/solicitar-acceso', methods=['GET', 'POST'])
def solicitar():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        # Honeypot anti-bots: los humanos no ven este campo
        if request.form.get('empresa_web'):
            return render_template('registro/confirmacion.html')

        nombre_negocio = (request.form.get('nombre_negocio') or '').strip()
        nombre = (request.form.get('nombre') or '').strip()
        apellido = (request.form.get('apellido') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        telefono = (request.form.get('telefono') or '').strip()
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        password2 = request.form.get('password2') or ''

        # Validaciones
        errores = []
        if not nombre_negocio:
            errores.append('El nombre del negocio es obligatorio.')
        if not nombre or not apellido:
            errores.append('Tu nombre y apellido son obligatorios.')
        if not email or '@' not in email:
            errores.append('Ingresa un email válido.')
        if not username or len(username) < 3:
            errores.append('El nombre de usuario debe tener al menos 3 caracteres.')
        if len(password) < 8:
            errores.append('La contraseña debe tener al menos 8 caracteres.')
        if password != password2:
            errores.append('Las contraseñas no coinciden.')

        if not errores:
            if Negocio.query.filter_by(nombre=nombre_negocio).first():
                errores.append('Ya existe una solicitud con ese nombre de negocio.')
            if User.query.filter_by(username=username).first():
                errores.append('Ese nombre de usuario ya está en uso.')
            if User.query.filter_by(email=email).first():
                errores.append('Ese email ya está registrado.')

        if errores:
            for e in errores:
                flash(e, 'danger')
            return render_template('registro/solicitar.html', datos=request.form)

        # Crear negocio pendiente + usuario administrador inactivo
        negocio = Negocio(
            nombre=nombre_negocio,
            slug=Negocio.generar_slug(nombre_negocio),
            email_contacto=email,
            telefono=telefono,
            estado='pendiente',
        )
        db.session.add(negocio)
        db.session.flush()  # obtener negocio.id

        usuario = User(
            negocio_id=negocio.id,
            username=username,
            email=email,
            nombre=nombre,
            apellido=apellido,
            is_admin=True,   # admin de su negocio
            activo=False,    # inactivo hasta que el superadmin apruebe
        )
        usuario.set_password(password)
        db.session.add(usuario)
        db.session.commit()

        # Aviso al dueño de la plataforma (no bloquea si falla)
        notificar_telegram(
            f'🔔 <b>Nueva solicitud de acceso</b>\n'
            f'Negocio: {negocio.nombre}\n'
            f'Responsable: {nombre} {apellido}\n'
            f'Email: {email}\n'
            f'Teléfono: {telefono or "—"}\n'
            f'Apruébala en el panel de administración: /admin/negocios'
        )

        return render_template('registro/confirmacion.html')

    return render_template('registro/solicitar.html', datos={})
