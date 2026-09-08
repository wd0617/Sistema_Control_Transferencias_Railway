from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # El superadmin también puede entrar (p. ej. en modo soporte)
        if not current_user.is_authenticated or not (current_user.is_admin or current_user.is_superadmin):
            flash('No tienes permisos para acceder a esta página.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def superadmin_required(f):
    """Solo para el dueño de la plataforma (gestión de negocios)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_superadmin:
            flash('No tienes permisos para acceder a esta página.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function
