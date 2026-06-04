from datetime import datetime
from app import db

class Transaccion(db.Model):
    __tablename__ = 'transacciones'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    servicio_id = db.Column(db.Integer, db.ForeignKey('servicios.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    comision = db.Column(db.Float, default=0)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    referencia = db.Column(db.String(64))
    notas = db.Column(db.Text)
    creado_por = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    def __repr__(self):
        return f'<Transaccion {self.id} - {self.monto}€>'

class Notificacion(db.Model):
    __tablename__ = 'notificaciones'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)  # 'recordatorio', 'alerta_limite', 'puede_enviar'
    mensaje = db.Column(db.Text, nullable=False)
    leida = db.Column(db.Boolean, default=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_lectura = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<Notificacion {self.id} - {self.tipo}>'
