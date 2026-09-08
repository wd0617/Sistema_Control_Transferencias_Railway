"""Tests de verificación para multitenancy, aislamiento de datos y límites.

Ejecutar con:
    .venv\\Scripts\\python -m unittest discover -s tests -p "test_*.py" -v
"""
import unittest
from datetime import date, datetime, timedelta
from flask import session
from flask_login import login_user, logout_user

from app import create_app
from app.extensions import db
from app.models.negocio import Negocio
from app.models.user import User
from app.models.cliente import Cliente, Servicio
from app.models.transaccion import Transaccion
from app.utils.tenancy import query_negocio, get_negocio_o_404, current_negocio_id


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = 'db/test_uploads'
    LIMITE_TRANSFERENCIA_SEMANAL = 999.0
    DIAS_REESTABLECIMIENTO = 7
    DIAS_ALERTA_VENCIMIENTO = 30


class MultitenancySmokeTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Negocios de prueba
        self.negocio_a = Negocio(
            nombre='Negocio Alfa', slug='negocio-alfa', estado='aprobado'
        )
        self.negocio_b = Negocio(
            nombre='Negocio Beta', slug='negocio-beta', estado='aprobado'
        )
        db.session.add_all([self.negocio_a, self.negocio_b])
        db.session.commit()

        # Usuarios
        self.user_a = User(
            username='user_alfa',
            email='alfa@test.com',
            negocio_id=self.negocio_a.id,
            activo=True
        )
        self.user_a.set_password('password123')

        self.user_b = User(
            username='user_beta',
            email='beta@test.com',
            negocio_id=self.negocio_b.id,
            activo=True
        )
        self.user_b.set_password('password123')

        self.superadmin = User(
            username='superadmin',
            email='super@test.com',
            is_superadmin=True,
            is_admin=True,
            activo=True
        )
        self.superadmin.set_password('superpass')

        db.session.add_all([self.user_a, self.user_b, self.superadmin])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_aislamiento_de_datos_entre_negocios(self):
        """Verifica que cada negocio solo vea sus propios clientes."""
        with self.app.test_request_context('/'):
            # Crear clientes asociados a cada negocio
            cliente_a = Cliente(
                negocio_id=self.negocio_a.id,
                nombre='Carlos',
                apellido='Alfa',
                documento='11111111A',
                fecha_nacimiento=date(1985, 5, 20)
            )
            cliente_b = Cliente(
                negocio_id=self.negocio_b.id,
                nombre='Beatriz',
                apellido='Beta',
                documento='22222222B',
                fecha_nacimiento=date(1990, 8, 15)
            )
            db.session.add_all([cliente_a, cliente_b])
            db.session.commit()

            # Autenticado como Usuario A
            login_user(self.user_a)
            self.assertEqual(current_negocio_id(), self.negocio_a.id)
            clientes_a = query_negocio(Cliente).all()
            self.assertEqual(len(clientes_a), 1)
            self.assertEqual(clientes_a[0].nombre, 'Carlos')

            # Usuario A no puede acceder al cliente de B vía get_negocio_o_404
            from werkzeug.exceptions import NotFound
            with self.assertRaises(NotFound):
                get_negocio_o_404(Cliente, cliente_b.id)

            logout_user()

            # Autenticado como Usuario B
            login_user(self.user_b)
            self.assertEqual(current_negocio_id(), self.negocio_b.id)
            clientes_b = query_negocio(Cliente).all()
            self.assertEqual(len(clientes_b), 1)
            self.assertEqual(clientes_b[0].nombre, 'Beatriz')
            logout_user()

    def test_superadmin_modo_soporte(self):
        """El superadmin ve todo o filtra según el negocio en soporte."""
        with self.app.test_request_context('/'):
            c_a = Cliente(
                negocio_id=self.negocio_a.id,
                nombre='Cliente A',
                apellido='Test',
                documento='DOCA1',
                fecha_nacimiento=date(1980, 1, 1)
            )
            c_b = Cliente(
                negocio_id=self.negocio_b.id,
                nombre='Cliente B',
                apellido='Test',
                documento='DOCB1',
                fecha_nacimiento=date(1980, 1, 1)
            )
            db.session.add_all([c_a, c_b])
            db.session.commit()

            login_user(self.superadmin)

            # Sin modo soporte: ve ambos
            todos = query_negocio(Cliente).all()
            self.assertEqual(len(todos), 2)

            # Activar modo soporte para Negocio A
            session['negocio_vista'] = self.negocio_a.id
            solo_a = query_negocio(Cliente).all()
            self.assertEqual(len(solo_a), 1)
            self.assertEqual(solo_a[0].documento, 'DOCA1')

            logout_user()

    def test_estampado_automatico_negocio_id(self):
        """Al crear un registro dentro de una request, se estampa el negocio_id del usuario."""
        with self.app.test_request_context('/'):
            login_user(self.user_a)

            nuevo_cliente = Cliente(
                nombre='Manuel',
                apellido='Gomez',
                documento='33333333C',
                fecha_nacimiento=date(1992, 3, 10)
            )
            db.session.add(nuevo_cliente)
            db.session.commit()

            self.assertIsNotNone(nuevo_cliente.negocio_id)
            self.assertEqual(nuevo_cliente.negocio_id, self.negocio_a.id)
            logout_user()

    def test_limite_semanal_transferencias(self):
        """Verifica la regla de 999 € acumulados en ventana móvil de 7 días."""
        with self.app.test_request_context('/'):
            login_user(self.user_a)

            servicio = Servicio(
                nombre='Western Union Test',
                comision_porcentaje=5.0,
                activo=True
            )
            cliente = Cliente(
                nombre='David',
                apellido='Lopez',
                documento='44444444D',
                fecha_nacimiento=date(1988, 7, 25)
            )
            db.session.add_all([servicio, cliente])
            db.session.commit()

            # Sin transferencias previas: saldo disponible debe ser 999 €
            self.assertEqual(cliente.calcular_saldo_disponible(), 999.0)

            # Registrar primera transferencia de 600 €
            tx1 = Transaccion(
                negocio_id=self.negocio_a.id,
                cliente_id=cliente.id,
                servicio_id=servicio.id,
                monto=600.0,
                comision=30.0,
                fecha=datetime.utcnow() - timedelta(days=2)
            )
            db.session.add(tx1)
            db.session.commit()

            # Saldo disponible restante: 999 - 600 = 399 €
            self.assertEqual(cliente.calcular_saldo_disponible(), 399.0)
            self.assertGreater(cliente.dias_hasta_reestablecimiento(), 0)

            # Registrar segunda transferencia de 300 €
            tx2 = Transaccion(
                negocio_id=self.negocio_a.id,
                cliente_id=cliente.id,
                servicio_id=servicio.id,
                monto=300.0,
                comision=15.0,
                fecha=datetime.utcnow() - timedelta(days=1)
            )
            db.session.add(tx2)
            db.session.commit()

            # Saldo disponible restante: 399 - 300 = 99 €
            self.assertEqual(cliente.calcular_saldo_disponible(), 99.0)

            logout_user()


if __name__ == '__main__':
    unittest.main()
