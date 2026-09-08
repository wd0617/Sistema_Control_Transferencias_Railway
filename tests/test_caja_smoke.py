"""Tests automatizados para el módulo de Arqueo y Cierre de Caja Diario.

Ejecutar con:
    .venv\\Scripts\\python -m unittest tests.test_caja_smoke -v
"""
import unittest
from datetime import datetime, timedelta
from flask_login import login_user, logout_user

from app import create_app
from app.extensions import db
from app.models.negocio import Negocio
from app.models.user import User
from app.models.cliente import Cliente, Servicio
from app.models.transaccion import Transaccion
from app.models.producto import Producto, MovimientoProducto
from app.models.caja import CajaSesion, MovimientoCaja
from app.utils.tenancy import query_negocio, get_negocio_o_404


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = 'db/test_uploads'


class CajaSmokeTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Negocios
        self.negocio_a = Negocio(nombre='Negocio A', slug='negocio-a', estado='aprobado')
        self.negocio_b = Negocio(nombre='Negocio B', slug='negocio-b', estado='aprobado')
        db.session.add_all([self.negocio_a, self.negocio_b])
        db.session.commit()

        # Usuarios
        self.user_a = User(
            username='cajero_a', email='cajero_a@test.com',
            negocio_id=self.negocio_a.id, activo=True
        )
        self.user_a.set_password('pass123')

        self.user_b = User(
            username='cajero_b', email='cajero_b@test.com',
            negocio_id=self.negocio_b.id, activo=True
        )
        self.user_b.set_password('pass123')

        db.session.add_all([self.user_a, self.user_b])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_flujo_completo_caja_cuadrada(self):
        """Prueba apertura, recaudaciones (tx + ventas + movs) y arqueo cuadrado."""
        with self.app.test_request_context('/'):
            login_user(self.user_a)

            # 1. Apertura con 200 €
            caja = CajaSesion(
                negocio_id=self.negocio_a.id,
                usuario_apertura_id=self.user_a.id,
                monto_inicial=200.0,
                estado='abierta'
            )
            db.session.add(caja)
            db.session.commit()

            self.assertTrue(caja.esta_abierta)

            # 2. Transferencia: 100 € monto + 5 € comisión = 105 € cobrados
            servicio = Servicio(negocio_id=self.negocio_a.id, nombre='Western Union')
            cliente = Cliente(negocio_id=self.negocio_a.id, nombre='Ana', apellido='García', documento='12345678Z', fecha_nacimiento=datetime(1990, 1, 1).date())
            db.session.add_all([servicio, cliente])
            db.session.commit()

            tx = Transaccion(
                negocio_id=self.negocio_a.id,
                cliente_id=cliente.id,
                servicio_id=servicio.id,
                monto=100.0,
                comision=5.0,
                fecha=datetime.utcnow()
            )
            db.session.add(tx)

            # 3. Venta de producto: 15 €
            producto = Producto(negocio_id=self.negocio_a.id, nombre='Snack', precio=15.0)
            db.session.add(producto)
            db.session.commit()

            venta = MovimientoProducto(
                negocio_id=self.negocio_a.id,
                producto_id=producto.id,
                tipo='venta',
                cantidad=1.0,
                total=15.0,
                fecha=datetime.utcnow()
            )
            db.session.add(venta)

            # 4. Movimientos manuales: +20 € aporte, -10 € gasto
            mov_in = MovimientoCaja(
                negocio_id=self.negocio_a.id,
                caja_sesion_id=caja.id,
                tipo='entrada',
                concepto='Aporte de cambio',
                monto=20.0,
                usuario_id=self.user_a.id
            )
            mov_out = MovimientoCaja(
                negocio_id=self.negocio_a.id,
                caja_sesion_id=caja.id,
                tipo='salida',
                concepto='Compra de folios',
                monto=10.0,
                usuario_id=self.user_a.id
            )
            db.session.add_all([mov_in, mov_out])
            db.session.commit()

            # 5. Cálculo del resumen
            # Esperado: 200 (inicial) + 105 (tx) + 15 (venta) + 20 (in) - 10 (out) = 330.0 €
            resumen = caja.calcular_resumen()
            self.assertEqual(resumen['monto_inicial'], 200.0)
            self.assertEqual(resumen['total_transferencias'], 105.0)
            self.assertEqual(resumen['total_ventas'], 15.0)
            self.assertEqual(resumen['total_entradas_manuales'], 20.0)
            self.assertEqual(resumen['total_salidas_manuales'], 10.0)
            self.assertEqual(resumen['efectivo_esperado'], 330.0)

            # Verificar desglose por empresa remesadora (a depositar)
            self.assertEqual(len(resumen['desglose_servicios']), 1)
            wu_desglose = resumen['desglose_servicios'][0]
            self.assertEqual(wu_desglose['nombre'], 'Western Union')
            self.assertEqual(wu_desglose['monto_enviado'], 100.0)
            self.assertEqual(wu_desglose['total_cobrado'], 105.0)
            self.assertEqual(resumen['total_principal_remesas'], 100.0)

            # 6. Cierre con exactamente 330.0 €
            caja.fecha_cierre = datetime.utcnow()
            caja.usuario_cierre_id = self.user_a.id
            caja.monto_esperado = resumen['efectivo_esperado']
            caja.monto_real = 330.0
            caja.diferencia = round(caja.monto_real - caja.monto_esperado, 2)
            caja.estado = 'cerrada'
            db.session.commit()

            self.assertEqual(caja.diferencia, 0.0)
            self.assertFalse(caja.esta_abierta)

            logout_user()

    def test_arqueo_con_faltante_y_sobrante(self):
        """Valida detección de descuadres (sobrante > 0, faltante < 0)."""
        with self.app.test_request_context('/'):
            login_user(self.user_a)

            # Caja con faltante
            caja_faltante = CajaSesion(
                negocio_id=self.negocio_a.id,
                usuario_apertura_id=self.user_a.id,
                monto_inicial=100.0,
                estado='abierta'
            )
            db.session.add(caja_faltante)
            db.session.commit()

            resumen = caja_faltante.calcular_resumen()
            self.assertEqual(resumen['efectivo_esperado'], 100.0)

            # Se cuentan 95 € (faltan 5 €)
            caja_faltante.monto_esperado = 100.0
            caja_faltante.monto_real = 95.0
            caja_faltante.diferencia = round(caja_faltante.monto_real - caja_faltante.monto_esperado, 2)
            caja_faltante.estado = 'cerrada'
            db.session.commit()

            self.assertEqual(caja_faltante.diferencia, -5.0)

            # Caja con sobrante
            caja_sobrante = CajaSesion(
                negocio_id=self.negocio_a.id,
                usuario_apertura_id=self.user_a.id,
                monto_inicial=100.0,
                estado='abierta'
            )
            db.session.add(caja_sobrante)
            db.session.commit()

            # Se cuentan 112.50 € (sobran 12.50 €)
            caja_sobrante.monto_esperado = 100.0
            caja_sobrante.monto_real = 112.50
            caja_sobrante.diferencia = round(caja_sobrante.monto_real - caja_sobrante.monto_esperado, 2)
            caja_sobrante.estado = 'cerrada'
            db.session.commit()

            self.assertEqual(caja_sobrante.diferencia, 12.50)

            logout_user()

    def test_aislamiento_multitenant_caja(self):
        """El negocio B no puede ver ni acceder a la caja del negocio A."""
        with self.app.test_request_context('/'):
            # Negocio A abre caja
            login_user(self.user_a)
            caja_a = CajaSesion(
                negocio_id=self.negocio_a.id,
                usuario_apertura_id=self.user_a.id,
                monto_inicial=150.0,
                estado='abierta'
            )
            db.session.add(caja_a)
            db.session.commit()

            self.assertEqual(query_negocio(CajaSesion).count(), 1)
            logout_user()

            # Negocio B no ve ninguna caja abierta
            login_user(self.user_b)
            self.assertEqual(query_negocio(CajaSesion).count(), 0)

            # Negocio B intenta acceder al ID de la caja de A
            from werkzeug.exceptions import NotFound
            with self.assertRaises(NotFound):
                get_negocio_o_404(CajaSesion, caja_a.id)

            logout_user()


if __name__ == '__main__':
    unittest.main()
