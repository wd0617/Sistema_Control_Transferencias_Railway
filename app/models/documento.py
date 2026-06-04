from datetime import datetime, date
from app.extensions import db

class DocumentoCliente(db.Model):
    """Modelo para gestionar documentos de identidad de clientes con control de vencimiento."""
    __tablename__ = 'documentos_cliente'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    
    # Información del documento
    tipo_documento = db.Column(db.String(50), nullable=False)  # NIE, Pasaporte, DNI, Permiso Residencia
    numero_documento = db.Column(db.String(50), nullable=False)
    pais_emision = db.Column(db.String(100), default='España')
    
    # Fechas
    fecha_emision = db.Column(db.Date)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    
    # Archivos
    foto_anverso = db.Column(db.String(255))  # Ruta al archivo
    foto_reverso = db.Column(db.String(255))  # Ruta al archivo
    
    # Estado y control
    estado = db.Column(db.String(20), default='vigente')  # vigente, por_vencer, vencido
    es_documento_principal = db.Column(db.Boolean, default=False)
    notas = db.Column(db.Text)
    
    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    actualizado_por = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relación con cliente
    cliente = db.relationship('Cliente', backref=db.backref('documentos', lazy='dynamic'))
    
    # Tipos de documento disponibles
    TIPOS_DOCUMENTO = [
        ('NIE', 'NIE - Número de Identidad de Extranjero'),
        ('DNI', 'DNI - Documento Nacional de Identidad'),
        ('PASAPORTE', 'Pasaporte'),
        ('PERMISO_RESIDENCIA', 'Permiso de Residencia'),
        ('TARJETA_COMUNITARIA', 'Tarjeta Comunitaria'),
        ('OTRO', 'Otro documento')
    ]
    
    def __repr__(self):
        return f'<Documento {self.tipo_documento} - {self.numero_documento}>'
    
    @property
    def dias_hasta_vencimiento(self):
        """Calcula los días restantes hasta el vencimiento."""
        if not self.fecha_vencimiento:
            return None
        hoy = date.today()
        delta = self.fecha_vencimiento - hoy
        return delta.days
    
    @property
    def esta_vencido(self):
        """Verifica si el documento está vencido."""
        dias = self.dias_hasta_vencimiento
        return dias is not None and dias < 0
    
    @property
    def esta_por_vencer(self, dias_alerta=30):
        """Verifica si el documento está próximo a vencer."""
        dias = self.dias_hasta_vencimiento
        return dias is not None and 0 <= dias <= dias_alerta
    
    def actualizar_estado(self, dias_alerta=30):
        """Actualiza el estado del documento basándose en la fecha de vencimiento."""
        dias = self.dias_hasta_vencimiento
        
        if dias is None:
            self.estado = 'desconocido'
        elif dias < 0:
            self.estado = 'vencido'
        elif dias <= dias_alerta:
            self.estado = 'por_vencer'
        else:
            self.estado = 'vigente'
        
        return self.estado
    
    @staticmethod
    def obtener_documentos_por_vencer(dias=30):
        """Obtiene todos los documentos que vencerán en los próximos X días."""
        from datetime import timedelta
        fecha_limite = date.today() + timedelta(days=dias)
        
        return DocumentoCliente.query.filter(
            DocumentoCliente.fecha_vencimiento <= fecha_limite,
            DocumentoCliente.fecha_vencimiento >= date.today()
        ).order_by(DocumentoCliente.fecha_vencimiento).all()
    
    @staticmethod
    def obtener_documentos_vencidos():
        """Obtiene todos los documentos vencidos."""
        return DocumentoCliente.query.filter(
            DocumentoCliente.fecha_vencimiento < date.today()
        ).order_by(DocumentoCliente.fecha_vencimiento).all()
    
    @staticmethod
    def contar_por_estado():
        """Cuenta documentos por estado."""
        from sqlalchemy import func
        hoy = date.today()
        from datetime import timedelta
        fecha_alerta = hoy + timedelta(days=30)
        
        vencidos = DocumentoCliente.query.filter(
            DocumentoCliente.fecha_vencimiento < hoy
        ).count()
        
        por_vencer = DocumentoCliente.query.filter(
            DocumentoCliente.fecha_vencimiento >= hoy,
            DocumentoCliente.fecha_vencimiento <= fecha_alerta
        ).count()
        
        vigentes = DocumentoCliente.query.filter(
            DocumentoCliente.fecha_vencimiento > fecha_alerta
        ).count()
        
        return {
            'vencidos': vencidos,
            'por_vencer': por_vencer,
            'vigentes': vigentes,
            'total': vencidos + por_vencer + vigentes
        }
