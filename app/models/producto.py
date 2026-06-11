from datetime import datetime
from app import db


class Producto(db.Model):
    __tablename__ = 'productos'

    CATEGORIAS = [
        ('frescos', 'Frescos (naturales por kg)'),
        ('procesados', 'Procesados (por unidad)'),
        ('cosmetica_ropa', 'Cosmética / Ropa'),
        ('servicios', 'Servicios'),
    ]

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(30), default='procesados')
    tipo_medida = db.Column(db.String(20), default='unidad')  # 'unidad' | 'peso'
    precio = db.Column(db.Float, nullable=False)
    stock_actual = db.Column(db.Float, default=0)
    foto = db.Column(db.String(255))
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    movimientos = db.relationship('MovimientoProducto', backref='producto', lazy='dynamic',
                                  cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Producto {self.nombre}>'

    def label_medida(self):
        return 'kg' if self.tipo_medida == 'peso' else 'u'

    def label_categoria(self):
        for val, label in self.CATEGORIAS:
            if val == self.categoria:
                return label
        return self.categoria


class MovimientoProducto(db.Model):
    __tablename__ = 'movimientos_producto'

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'entrada' | 'venta'
    cantidad = db.Column(db.Float, nullable=False)
    precio_unitario_momento = db.Column(db.Float)
    total = db.Column(db.Float)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    notas = db.Column(db.String(255))
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    usuario = db.relationship('User', backref='movimientos_producto')

    def __repr__(self):
        return f'<MovimientoProducto {self.tipo} {self.cantidad}>'
