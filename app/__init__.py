import os
from flask import Flask
from config import Config
from app.extensions import db, login_manager, migrate, csrf
from flask_cors import CORS

def create_app(config_class=Config):
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
    app.config.from_object(config_class)
    
    # Configurar Cloudinary si hay credenciales
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
    api_key = os.environ.get('CLOUDINARY_API_KEY')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')
    if cloud_name and api_key and api_secret:
        import cloudinary
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
    
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
    from app.routes.productos import productos as productos_blueprint
    
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)
    app.register_blueprint(clientes_blueprint, url_prefix='/clientes')
    app.register_blueprint(transacciones_blueprint, url_prefix='/transacciones')
    app.register_blueprint(servicios_blueprint, url_prefix='/servicios')
    app.register_blueprint(calculadora_blueprint, url_prefix='/calculadora')
    app.register_blueprint(documentos_blueprint, url_prefix='/documentos')
    app.register_blueprint(data_mgmt_blueprint, url_prefix='/datos')
    app.register_blueprint(notificaciones_blueprint, url_prefix='/notificaciones')
    app.register_blueprint(productos_blueprint, url_prefix='/productos')
    
    # Crear tablas que no existan y aplicar migraciones pendientes
    with app.app_context():
        db.create_all()
        try:
            from flask_migrate import upgrade
            upgrade()
        except Exception:
            pass
        
        # Fallback: asegurar columnas nuevas en tablas existentes
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            with db.engine.begin() as conn:
                if 'productos' in inspector.get_table_names():
                    cols = [c['name'] for c in inspector.get_columns('productos')]
                    if 'categoria' not in cols:
                        conn.execute(text("ALTER TABLE productos ADD COLUMN categoria VARCHAR(30)"))
                    if 'foto' not in cols:
                        conn.execute(text("ALTER TABLE productos ADD COLUMN foto VARCHAR(255)"))
                if 'movimientos_producto' in inspector.get_table_names():
                    cols_mov = [c['name'] for c in inspector.get_columns('movimientos_producto')]
                    if 'unidades' not in cols_mov:
                        conn.execute(text("ALTER TABLE movimientos_producto ADD COLUMN unidades INTEGER"))
        except Exception:
            pass
    
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

