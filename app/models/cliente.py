from datetime import datetime
from app import db

# Tabla de relación muchos a muchos entre clientes y servicios
cliente_servicio = db.Table('cliente_servicio',
    db.Column('cliente_id', db.Integer, db.ForeignKey('clientes.id'), primary_key=True),
    db.Column('servicio_id', db.Integer, db.ForeignKey('servicios.id'), primary_key=True)
)

class Cliente(db.Model):
    __tablename__ = 'clientes'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(64), nullable=False)
    apellido = db.Column(db.String(64), nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=False)
    documento = db.Column(db.String(20), unique=True, nullable=False)
    tipo_documento = db.Column(db.String(50), default='NIE')  # NIE, DNI, Pasaporte, etc.
    documento_fecha_emision = db.Column(db.Date)  # Fecha de emisión del documento
    documento_fecha_vencimiento = db.Column(db.Date)  # Fecha de vencimiento del documento
    telefono = db.Column(db.String(20))
    foto_documento = db.Column(db.String(255))  # Ruta al archivo de imagen
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    ultima_visita = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Tipos de documento disponibles
    TIPOS_DOCUMENTO = [
        ('NIE', 'NIE - Número de Identidad de Extranjero'),
        ('DNI', 'DNI - Documento Nacional de Identidad'),
        ('PASAPORTE', 'Pasaporte'),
        ('PERMISO_RESIDENCIA', 'Permiso de Residencia'),
        ('TARJETA_COMUNITARIA', 'Tarjeta Comunitaria'),
        ('OTRO', 'Otro documento')
    ]
    
    @property
    def dias_hasta_vencimiento(self):
        """Calcula los días restantes hasta el vencimiento del documento."""
        if not self.documento_fecha_vencimiento:
            return None
        from datetime import date
        delta = self.documento_fecha_vencimiento - date.today()
        return delta.days
    
    @property
    def documento_vencido(self):
        """Verifica si el documento está vencido."""
        dias = self.dias_hasta_vencimiento
        if dias is None:
            return False
        return dias < 0
    
    @property
    def documento_por_vencer(self):
        """Verifica si el documento está próximo a vencer (dentro de 30 días)."""
        dias = self.dias_hasta_vencimiento
        if dias is None:
            return False
        return 0 <= dias <= 30
    
    @property
    def estado_documento(self):
        """Devuelve el estado del documento: vencido, por_vencer, vigente, sin_fecha."""
        if not self.documento_fecha_vencimiento:
            return 'sin_fecha'
        dias = self.dias_hasta_vencimiento
        if dias < 0:
            return 'vencido'
        elif dias <= 30:
            return 'por_vencer'
        else:
            return 'vigente'
    
    @classmethod
    def get_documentos_vencidos(cls):
        """Obtiene todos los clientes con documentos vencidos."""
        from datetime import date
        return cls.query.filter(
            cls.documento_fecha_vencimiento < date.today()
        ).all()
    
    @classmethod
    def get_documentos_por_vencer(cls, dias=30):
        """Obtiene todos los clientes con documentos próximos a vencer."""
        from datetime import date, timedelta
        fecha_limite = date.today() + timedelta(days=dias)
        return cls.query.filter(
            cls.documento_fecha_vencimiento >= date.today(),
            cls.documento_fecha_vencimiento <= fecha_limite
        ).all()
    
    # Relaciones
    servicios = db.relationship('Servicio', secondary=cliente_servicio, lazy='subquery',
                               backref=db.backref('clientes', lazy=True))
    transacciones = db.relationship('Transaccion', backref='cliente', lazy='dynamic')
    
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"
    
    def calcular_saldo_disponible(self, limite_semanal=999):
        from app.models.transaccion import Transaccion
        from datetime import datetime, timedelta
        
        # Obtener la fecha de hace una semana
        fecha_inicio = datetime.utcnow() - timedelta(days=7)
        
        # Calcular la suma de transacciones en la última semana
        suma_transacciones = db.session.query(db.func.sum(Transaccion.monto)) \
            .filter(Transaccion.cliente_id == self.id) \
            .filter(Transaccion.fecha >= fecha_inicio) \
            .scalar() or 0
            
        return limite_semanal - suma_transacciones
    
    def dias_hasta_reestablecimiento(self):
        from app.models.transaccion import Transaccion
        from datetime import datetime, timedelta
        
        # Obtener la transacción más antigua dentro de la semana
        fecha_inicio = datetime.utcnow() - timedelta(days=7)
        
        transaccion_antigua = Transaccion.query \
            .filter(Transaccion.cliente_id == self.id) \
            .filter(Transaccion.fecha >= fecha_inicio) \
            .order_by(Transaccion.fecha) \
            .first()
            
        if not transaccion_antigua:
            return 0
            
        # Calcular días hasta que la transacción más antigua salga de la ventana de 7 días
        dias_restantes = 7 - (datetime.utcnow() - transaccion_antigua.fecha).days
        return max(0, dias_restantes)
    
    def __repr__(self):
        return f'<Cliente {self.nombre} {self.apellido}>'

class Servicio(db.Model):
    __tablename__ = 'servicios'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(64), unique=True, nullable=False)
    descripcion = db.Column(db.String(255))
    comision_porcentaje = db.Column(db.Float, default=0)
    activo = db.Column(db.Boolean, default=True)
    
    # Transacciones relacionadas con este servicio
    transacciones = db.relationship('Transaccion', backref='servicio', lazy='dynamic')
    
    def __repr__(self):
        return f'<Servicio {self.nombre}>'
