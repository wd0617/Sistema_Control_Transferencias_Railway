from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User, ActivityLog
from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=user.id,
                activity='Inicio de sesión',
                ip_address=request.remote_addr
            )
            db.session.add(activity)
            db.session.commit()
            
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('main.dashboard')
            return redirect(next_page)
        flash('Usuario o contraseña incorrectos', 'danger')
    
    return render_template('auth/login.html', now=datetime.now())

@auth.route('/logout')
@login_required
def logout():
    # Registrar actividad
    activity = ActivityLog(
        user_id=current_user.id,
        activity='Cierre de sesión',
        ip_address=request.remote_addr
    )
    db.session.add(activity)
    db.session.commit()
    
    logout_user()
    flash('Has cerrado sesión exitosamente', 'info')
    return redirect(url_for('auth.login'))

@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user
    
    # Obtener registros de actividad del usuario
    activities = ActivityLog.query.filter_by(user_id=user.id).order_by(ActivityLog.timestamp.desc()).limit(10).all()
    
    if request.method == 'POST':
        # Actualizar información del usuario
        username = request.form.get('username')
        email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validar cambio de nombre de usuario
        if username != user.username:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('El nombre de usuario ya está en uso', 'danger')
                return redirect(url_for('auth.profile'))
            user.username = username
        
        # Actualizar email
        if email:
            user.email = email
        
        # Cambiar contraseña si se proporciona
        if current_password and new_password and confirm_password:
            if not user.check_password(current_password):
                flash('La contraseña actual es incorrecta', 'danger')
                return redirect(url_for('auth.profile'))
            
            if new_password != confirm_password:
                flash('Las nuevas contraseñas no coinciden', 'danger')
                return redirect(url_for('auth.profile'))
            
            user.password_hash = generate_password_hash(new_password)
            
            # Registrar actividad
            activity = ActivityLog(
                user_id=user.id,
                activity='Cambio de contraseña',
                ip_address=request.remote_addr
            )
            db.session.add(activity)
        
        # Registrar actividad de actualización de perfil
        activity = ActivityLog(
            user_id=user.id,
            activity='Actualización de perfil',
            ip_address=request.remote_addr
        )
        db.session.add(activity)
        
        db.session.commit()
        flash('Perfil actualizado correctamente', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/profile.html', user=user, activities=activities, now=datetime.now())
