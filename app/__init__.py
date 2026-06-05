import os
from flask import Flask
from config import Config
from app.extensions import db, login_manager, migrate, csrf
from flask_cors import CORS

def create_app(config_class=Config):
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
    app.config.from_object(config_class)
    
    # Asegurar que existe la carpeta de uploads
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Inicializar extensiones con la app
    db.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'info'
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    # Excluir endpoint AJAX de calculadora del CSRF (se maneja por separado)
    csrf.exempt('app.routes.calculadora.calculadora')
    
    # Registrar blueprints
    from app.routes.auth import auth as auth_blueprint
    from app.routes.main import main as main_blueprint
    from app.routes.clientes import clientes as clientes_blueprint
    from app.routes.transacciones import transacciones as transacciones_blueprint
    from app.routes.servicios import servicios as servicios_blueprint
    from app.routes.calculadora import calculadora as calculadora_blueprint
    from app.routes.documentos import documentos as documentos_blueprint
    from app.routes.data_management import data_mgmt as data_mgmt_blueprint
    from app.routes.notificaciones import notificaciones as notificaciones_blueprint
    
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)
    app.register_blueprint(clientes_blueprint, url_prefix='/clientes')
    app.register_blueprint(transacciones_blueprint, url_prefix='/transacciones')
    app.register_blueprint(servicios_blueprint, url_prefix='/servicios')
    app.register_blueprint(calculadora_blueprint, url_prefix='/calculadora')
    app.register_blueprint(documentos_blueprint, url_prefix='/documentos')
    app.register_blueprint(data_mgmt_blueprint, url_prefix='/datos')
    app.register_blueprint(notificaciones_blueprint, url_prefix='/notificaciones')
    
    # Crear la base de datos si no existe
    with app.app_context():
        db.create_all()
    
    # Inyectar contador de notificaciones en todos los templates
    @app.context_processor
    def inject_notificaciones():
        from app.utils.notificaciones import contar_notificaciones_pendientes
        from flask_login import current_user
        if current_user.is_authenticated:
            return {'notificaciones_count': contar_notificaciones_pendientes()}
        return {'notificaciones_count': 0}
    
    # Inyectar 'now' en todos los templates para el footer
    @app.context_processor
    def inject_now():
        from datetime import datetime
        return {'now': datetime.now()}
    
    return app

