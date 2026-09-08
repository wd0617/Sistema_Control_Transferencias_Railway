"""Tests para generación de mensajes y enlaces de WhatsApp en italiano y español.

Ejecutar con:
    .venv\\Scripts\\python -m unittest tests/test_whatsapp_cliente.py -v
"""
import unittest
from datetime import datetime
from app import create_app
from app.extensions import db
from app.models.negocio import Negocio
from app.models.user import User
from app.models.cliente import Cliente, Servicio
from app.models.transaccion import Transaccion
from app.utils.whatsapp_utils import (
    formatear_telefono_whatsapp,
    generar_mensaje_whatsapp,
    generar_url_whatsapp
)


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = 'db/test_uploads'


class WhatsAppClienteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.negocio = Negocio(nombre='Agenzia Roma', slug='agenzia-roma', estado='aprobado')
        db.session.add(self.negocio)
        db.session.commit()

        self.user = User(
            username='operatore1',
            email='op1@test.com',
            negocio_id=self.negocio.id,
            activo=True
        )
        self.user.set_password('pass123')
        db.session.add(self.user)

        self.servicio = Servicio(
            negocio_id=self.negocio.id,
            nombre='Western Union',
            comision_porcentaje=5.0
        )
        db.session.add(self.servicio)
        db.session.commit()

        self.cliente = Cliente(
            negocio_id=self.negocio.id,
            nombre='Marco',
            apellido='Rossi',
            documento='RSSMRC80A01H501U',
            telefono='3401234567',
            fecha_nacimiento=datetime(1980, 1, 1).date()
        )
        db.session.add(self.cliente)
        db.session.commit()

        self.transaccion = Transaccion(
            negocio_id=self.negocio.id,
            cliente_id=self.cliente.id,
            servicio_id=self.servicio.id,
            monto=300.0,
            comision=15.0,
            referencia='MTCN987654321',
            fecha=datetime(2026, 9, 8, 16, 0)
        )
        db.session.add(self.transaccion)
        db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_formatear_telefono_italiano(self):
        """Verifica que números italianos de 10 dígitos reciban el prefijo 39."""
        # 10 dígitos empezando en 3 (móvil italiano)
        self.assertEqual(formatear_telefono_whatsapp('3401234567'), '393401234567')
        self.assertEqual(formatear_telefono_whatsapp('+39 340 123 4567'), '393401234567')
        self.assertEqual(formatear_telefono_whatsapp('0039 340 123 4567'), '393401234567')

    def test_formatear_telefono_espanol(self):
        """Verifica que números españoles de 9 dígitos reciban el prefijo 34."""
        self.assertEqual(formatear_telefono_whatsapp('612345678'), '34612345678')
        self.assertEqual(formatear_telefono_whatsapp('+34 612 345 678'), '34612345678')

    def test_generar_mensaje_italiano(self):
        """Verifica que el mensaje en italiano contenga los datos y redacción correcta."""
        msg_it = generar_mensaje_whatsapp(self.transaccion, idioma='it')
        self.assertIn('Ciao Marco! 👋', msg_it)
        self.assertIn('Grazie per aver scelto la nostra agenzia.', msg_it)
        self.assertIn('Servizio: Western Union', msg_it)
        self.assertIn('Importo inviato: 300.00 €', msg_it)
        self.assertIn('Commissione: 15.00 €', msg_it)
        self.assertIn('Totale pagato: 315.00 €', msg_it)
        self.assertIn('Codice / MTCN: MTCN987654321', msg_it)
        self.assertIn('Grazie per la tua fiducia e a presto!', msg_it)

    def test_generar_mensaje_espanol(self):
        """Verifica que el mensaje en español contenga los datos y redacción correcta."""
        msg_es = generar_mensaje_whatsapp(self.transaccion, idioma='es')
        self.assertIn('¡Hola Marco! 👋', msg_es)
        self.assertIn('Gracias por elegir nuestra agencia.', msg_es)
        self.assertIn('Monto enviado: 300.00 €', msg_es)
        self.assertIn('Código / Referencia: MTCN987654321', msg_es)

    def test_generar_url_whatsapp(self):
        """Verifica que la URL generada sea válida con wa.me y contenga el número y texto codificado."""
        url = generar_url_whatsapp(self.transaccion, idioma='it')
        self.assertTrue(url.startswith('https://wa.me/393401234567?text='))
        self.assertIn('Ciao%20Marco', url)
        self.assertIn('Western%20Union', url)

    def test_ruta_whatsapp_redirect(self):
        """Verifica que el endpoint /transacciones/<id>/whatsapp redirija a wa.me."""
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user.id)
            sess['_fresh'] = True

        resp = self.client.get(f'/transacciones/{self.transaccion.id}/whatsapp?lang=it')
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.location.startswith('https://wa.me/393401234567'))


if __name__ == '__main__':
    unittest.main()
