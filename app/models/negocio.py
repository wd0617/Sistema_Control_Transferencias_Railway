from datetime import datetime
from app.extensions import db


class Negocio(db.Model):
    """Negocio (tenant) de la plataforma multi-negocio.

    Cada negocio tiene sus datos aislados por `negocio_id` en todas las
    tablas de dominio. El acceso se solicita públicamente y lo aprueba
    el superadmin desde el panel /admin/negocios.
    """
    __tablename__ = 'negocios'

    ESTADOS = [
        ('pendiente', 'Pendiente de aprobación'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
        ('suspendido', 'Suspendido'),
    ]

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    email_contacto = db.Column(db.String(120))
    telefono = db.Column(db.String(30))
    estado = db.Column(db.String(20), default='pendiente', nullable=False)
    notas_admin = db.Column(db.Text)  # Notas internas del superadmin (contrato, etc.)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    aprobado_at = db.Column(db.DateTime)

    usuarios = db.relationship('User', backref='negocio', lazy='dynamic')

    @property
    def esta_aprobado(self):
        return self.estado == 'aprobado'

    @staticmethod
    def generar_slug(nombre):
        """Genera un slug único a partir del nombre del negocio."""
        import re
        import unicodedata
        base = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')
        base = re.sub(r'[^a-zA-Z0-9]+', '-', base).strip('-').lower() or 'negocio'
        slug = base
        contador = 2
        while Negocio.query.filter_by(slug=slug).first():
            slug = f'{base}-{contador}'
            contador += 1
        return slug

    def __repr__(self):
        return f'<Negocio {self.nombre} ({self.estado})>'
