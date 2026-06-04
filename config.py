import os
from datetime import timedelta
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # ============================================
    # SEGURIDAD
    # ============================================
    # Usar variable de entorno o generar una clave temporal (solo desarrollo)
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()
    
    # ============================================
    # BASE DE DATOS
    # ============================================
    # Determinar el entorno y configurar la BD apropiada
    @staticmethod
    def get_database_uri():
        # Primero intentar desde variable de entorno
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            # Algunos servicios (como Heroku) usan 'postgres://' en lugar de 'postgresql://'
            # SQLAlchemy requiere 'postgresql://'
            if db_url.startswith('postgres://'):
                db_url = db_url.replace('postgres://', 'postgresql://', 1)
            
            # Para conexiones a Neon.tech, asegurar SSL si no está configurado
            if 'neon.tech' in db_url and 'sslmode=' not in db_url:
                separator = '&' if '?' in db_url else '?'
                db_url += f'{separator}sslmode=require'
            
            return db_url
        
        # Si estamos en PythonAnywhere
        if 'PYTHONANYWHERE_SITE' in os.environ:
            return 'sqlite:////' + os.path.join(os.path.expanduser('~'), 'Sistema_Control_Transferencias', 'app.db')
        
        # Desarrollo local - SQLite
        return 'sqlite:///' + os.path.join(basedir, 'db', 'sistema_transferencias.db')
    
    SQLALCHEMY_DATABASE_URI = property(lambda self: Config.get_database_uri())
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuración del pool de conexiones (crítico para PythonAnywhere + MySQL)
    # PythonAnywhere cierra conexiones inactivas después de ~300 segundos
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,        # Verifica que la conexión esté viva antes de usarla
        'pool_recycle': 280,          # Recicla conexiones antes de los 300 segundos
        'pool_timeout': 30,           # Tiempo máximo esperando una conexión del pool
    }
    
    # ============================================
    # CONFIGURACIÓN DE ARCHIVOS
    # ============================================
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(basedir, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    
    # ============================================
    # CONFIGURACIÓN DE SESIÓN
    # ============================================
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # ============================================
    # LÍMITES DE TRANSFERENCIA
    # ============================================
    LIMITE_TRANSFERENCIA_SEMANAL = int(os.environ.get('LIMITE_TRANSFERENCIA_SEMANAL', 999))
    DIAS_REESTABLECIMIENTO = int(os.environ.get('DIAS_REESTABLECIMIENTO', 7))
    
    # ============================================
    # CONFIGURACIÓN DE DOCUMENTOS
    # ============================================
    # Días antes de vencimiento para alertar
    DIAS_ALERTA_VENCIMIENTO = int(os.environ.get('DIAS_ALERTA_VENCIMIENTO', 30))


# Inicializar la URI de la base de datos
Config.SQLALCHEMY_DATABASE_URI = Config.get_database_uri()
