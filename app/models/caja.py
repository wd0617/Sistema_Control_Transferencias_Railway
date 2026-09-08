from datetime import datetime
from app.extensions import db


class CajaSesion(db.Model):
    """Sesión de caja diaria o por turno para control de flujo de efectivo."""
    __tablename__ = 'caja_sesiones'

    id = db.Column(db.Integer, primary_key=True)
    negocio_id = db.Column(db.Integer, db.ForeignKey('negocios.id'), index=True, nullable=False)
    usuario_apertura_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    usuario_cierre_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    fecha_apertura = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_cierre = db.Column(db.DateTime, nullable=True)
    estado = db.Column(db.String(20), default='abierta', nullable=False)  # 'abierta' | 'cerrada'
    monto_inicial = db.Column(db.Float, default=0.0, nullable=False)
    monto_esperado = db.Column(db.Float, nullable=True)
    monto_real = db.Column(db.Float, nullable=True)
    diferencia = db.Column(db.Float, nullable=True)
    notas_apertura = db.Column(db.Text, nullable=True)
    notas_cierre = db.Column(db.Text, nullable=True)

    usuario_apertura = db.relationship('User', foreign_keys=[usuario_apertura_id], backref='cajas_abiertas')
    usuario_cierre = db.relationship('User', foreign_keys=[usuario_cierre_id], backref='cajas_cerradas')
    movimientos = db.relationship('MovimientoCaja', backref='caja_sesion', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def esta_abierta(self):
        return self.estado == 'abierta'

    def calcular_resumen(self):
        """Calcula el desglose financiero del periodo de la caja."""
        from app.models.transaccion import Transaccion
        from app.models.producto import MovimientoProducto
        from sqlalchemy import func

        fecha_fin = self.fecha_cierre or datetime.utcnow()

        # 1. Total recaudado por transferencias (monto + comisión cobrada)
        # Filtramos por negocio y por fecha dentro del turno
        q_tx = db.session.query(
            func.coalesce(func.sum(Transaccion.monto + Transaccion.comision), 0.0),
            func.count(Transaccion.id)
        ).filter(
            Transaccion.negocio_id == self.negocio_id,
            Transaccion.fecha >= self.fecha_apertura,
            Transaccion.fecha <= fecha_fin
        ).first()
        total_tx = float(q_tx[0] or 0.0)
        conteo_tx = int(q_tx[1] or 0)

        # 2. Total cobrado por ventas de productos
        q_prod = db.session.query(
            func.coalesce(func.sum(MovimientoProducto.total), 0.0),
            func.count(MovimientoProducto.id)
        ).filter(
            MovimientoProducto.negocio_id == self.negocio_id,
            MovimientoProducto.tipo == 'venta',
            MovimientoProducto.fecha >= self.fecha_apertura,
            MovimientoProducto.fecha <= fecha_fin
        ).first()
        total_ventas = float(q_prod[0] or 0.0)
        conteo_ventas = int(q_prod[1] or 0)

        # 3. Entradas y salidas manuales de caja
        movs = self.movimientos.all()
        total_entradas_manuales = sum(m.monto for m in movs if m.tipo == 'entrada')
        total_salidas_manuales = sum(m.monto for m in movs if m.tipo == 'salida')

        # 4. Efectivo esperado en caja
        efectivo_esperado = (
            self.monto_inicial
            + total_tx
            + total_ventas
            + total_entradas_manuales
            - total_salidas_manuales
        )

        return {
            'monto_inicial': self.monto_inicial,
            'total_transferencias': total_tx,
            'conteo_transferencias': conteo_tx,
            'total_ventas': total_ventas,
            'conteo_ventas': conteo_ventas,
            'total_entradas_manuales': total_entradas_manuales,
            'total_salidas_manuales': total_salidas_manuales,
            'efectivo_esperado': round(efectivo_esperado, 2)
        }

    def __repr__(self):
        return f'<CajaSesion {self.id} ({self.estado}) - Inicial: {self.monto_inicial}€>'


class MovimientoCaja(db.Model):
    """Entradas y salidas manuales de efectivo en caja."""
    __tablename__ = 'movimientos_caja'

    id = db.Column(db.Integer, primary_key=True)
    negocio_id = db.Column(db.Integer, db.ForeignKey('negocios.id'), index=True, nullable=False)
    caja_sesion_id = db.Column(db.Integer, db.ForeignKey('caja_sesiones.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'entrada' | 'salida'
    concepto = db.Column(db.String(200), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    usuario = db.relationship('User', backref='movimientos_caja')

    def __repr__(self):
        return f'<MovimientoCaja {self.tipo} {self.monto}€ - {self.concepto}>'
