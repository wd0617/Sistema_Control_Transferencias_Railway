"""Tests para búsqueda multi-documento y unificación de clientes duplicados.

Ejecutar con:
    .venv\\Scripts\\python -m unittest tests/test_clientes_unificacion.py -v
"""
import unittest
from datetime import date, datetime, timedelta
from app import create_app
from app.extensions import db
from app.models.negocio import Negocio
from app.models.user import User
from app.models.cliente import Cliente, Servicio
from app.models.documento import DocumentoCliente
from app.models.transaccion import Transaccion
from app.utils.cliente_utils import (
    obtener_o_crear_cliente_con_documento,
    fusionar_clientes,
    detectar_posibles_duplicados,
    _crear_documento_cliente
)


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


class ClientesUnificacionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.negocio = Negocio(nombre='Remesas Express', slug='remesas-express', estado='aprobado')
        self.negocio_otro = Negocio(nombre='Otro Negocio', slug='otro-negocio', estado='aprobado')
        db.session.add_all([self.negocio, self.negocio_otro])
        db.session.commit()

        self.user = User(
            username='cajero1',
            email='cajero1@test.com',
            negocio_id=self.negocio.id,
            activo=True,
            is_admin=True
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

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user.id)
            sess['_fresh'] = True

    def test_busqueda_multi_documento(self):
        """Verifica que buscar por un documento secundario encuentre al cliente."""
        self._login()

        # Crear cliente con documento principal NIE
        cliente = Cliente(
            negocio_id=self.negocio.id,
            nombre='Carlos',
            apellido='Santana',
            documento='X1234567A',
            tipo_documento='NIE',
            fecha_nacimiento=date(1985, 5, 20)
        )
        db.session.add(cliente)
        db.session.commit()

        # Vincular pasaporte como documento secundario
        _crear_documento_cliente(
            cliente=cliente,
            numero='PASSPORT999',
            tipo='PASAPORTE',
            fecha_emision=date(2020, 1, 1),
            fecha_vencimiento=date(2030, 1, 1)
        )
        db.session.commit()

        # 1. Búsqueda en /clientes/search con el pasaporte
        resp = self.client.get('/clientes/search?q=PASSPORT999')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Carlos Santana', resp.data)

        # 2. Búsqueda en /transacciones/api/buscar-cliente con el pasaporte
        resp_api = self.client.get('/transacciones/api/buscar-cliente?q=PASSPORT999')
        self.assertEqual(resp_api.status_code, 200)
        data = resp_api.get_json()
        self.assertEqual(len(data['resultados']), 1)
        self.assertEqual(data['resultados'][0]['nombre'], 'Carlos')
        self.assertIn('PASAPORTE PASSPORT999', data['resultados'][0]['coincidencia_secundaria'])

    def test_promover_documento_a_principal(self):
        """Verifica que hacer principal un documento secundario intercambie correctamente."""
        self._login()

        cliente = Cliente(
            negocio_id=self.negocio.id,
            nombre='Ana',
            apellido='Gomez',
            documento='DNI111111',
            tipo_documento='DNI',
            fecha_nacimiento=date(1990, 2, 15)
        )
        db.session.add(cliente)
        db.session.commit()

        # Añadir documento secundario mediante la ruta
        resp = self.client.post(f'/clientes/{cliente.id}/documentos/agregar', data={
            'tipo_documento': 'PASAPORTE',
            'numero_documento': 'PAS222222',
            'fecha_emision': '2021-01-01',
            'fecha_vencimiento': '2031-01-01'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Obtener el documento secundario
        doc_sec = DocumentoCliente.query.filter_by(cliente_id=cliente.id, numero_documento='PAS222222').first()
        self.assertIsNotNone(doc_sec)

        # Promover a principal
        resp_promover = self.client.post(f'/clientes/{cliente.id}/documentos/{doc_sec.id}/hacer-principal', follow_redirects=True)
        self.assertEqual(resp_promover.status_code, 200)

        db.session.refresh(cliente)
        self.assertEqual(cliente.documento, 'PAS222222')
        self.assertEqual(cliente.tipo_documento, 'PASAPORTE')

        # El antiguo principal DNI111111 debe estar ahora como secundario en DocumentoCliente
        antiguo_en_historial = DocumentoCliente.query.filter_by(cliente_id=cliente.id, numero_documento='DNI111111').first()
        self.assertIsNotNone(antiguo_en_historial)

    def test_fusion_clientes_duplicados(self):
        """Verifica que al fusionar dos perfiles, las transacciones se reasignen y el duplicado se elimine."""
        self._login()

        # Cliente A (Maestro)
        maestro = Cliente(
            negocio_id=self.negocio.id,
            nombre='Pedro',
            apellido='Alvarez',
            documento='NIE000001',
            tipo_documento='NIE',
            fecha_nacimiento=date(1980, 10, 5),
            telefono='600111222'
        )
        # Cliente B (Duplicado creado por error con su pasaporte)
        duplicado = Cliente(
            negocio_id=self.negocio.id,
            nombre='Pedro',
            apellido='Alvarez',
            documento='PAS999000',
            tipo_documento='PASAPORTE',
            fecha_nacimiento=date(1980, 10, 5),
            telefono='600111222'
        )
        db.session.add_all([maestro, duplicado])
        db.session.commit()

        # Transacción en maestro
        tx1 = Transaccion(
            negocio_id=self.negocio.id,
            cliente_id=maestro.id,
            servicio_id=self.servicio.id,
            monto=100.0,
            comision=5.0
        )
        # 2 transacciones en duplicado
        tx2 = Transaccion(
            negocio_id=self.negocio.id,
            cliente_id=duplicado.id,
            servicio_id=self.servicio.id,
            monto=250.0,
            comision=12.5
        )
        tx3 = Transaccion(
            negocio_id=self.negocio.id,
            cliente_id=duplicado.id,
            servicio_id=self.servicio.id,
            monto=50.0,
            comision=2.5
        )
        db.session.add_all([tx1, tx2, tx3])
        db.session.commit()

        dup_id = duplicado.id
        maestro_id = maestro.id

        # Ejecutar fusión
        resultado = fusionar_clientes(maestro, duplicado, user_id=self.user.id)
        self.assertTrue(resultado)

        # 1. El cliente duplicado debe estar eliminado
        self.assertIsNone(db.session.get(Cliente, dup_id))

        # 2. El cliente maestro debe tener ahora las 3 transacciones
        txs_maestro = Transaccion.query.filter_by(cliente_id=maestro_id).all()
        self.assertEqual(len(txs_maestro), 3)
        montos = sorted([t.monto for t in txs_maestro])
        self.assertEqual(montos, [50.0, 100.0, 250.0])

        # 3. El documento del duplicado (PAS999000) debe estar vinculado como DocumentoCliente del maestro
        doc_vinculado = DocumentoCliente.query.filter_by(cliente_id=maestro_id, numero_documento='PAS999000').first()
        self.assertIsNotNone(doc_vinculado)
        self.assertEqual(doc_vinculado.tipo_documento, 'PASAPORTE')

    def test_deteccion_duplicados_automaticos(self):
        """Verifica que detectar_posibles_duplicados encuentre clientes con mismo nombre o teléfono."""
        self._login()

        c1 = Cliente(negocio_id=self.negocio.id, nombre='Maria', apellido='Lopez', documento='DOC1', fecha_nacimiento=date(1995, 1, 1), telefono='655443322')
        c2 = Cliente(negocio_id=self.negocio.id, nombre='Maria', apellido='Lopez', documento='DOC2', fecha_nacimiento=date(1995, 1, 1), telefono='655443322')
        db.session.add_all([c1, c2])
        db.session.commit()

        # Debe detectar el grupo de duplicados
        grupos = detectar_posibles_duplicados()
        self.assertGreaterEqual(len(grupos), 1)
        ids_detectados = [c.id for c in grupos[0]['clientes']]
        self.assertIn(c1.id, ids_detectados)
        self.assertIn(c2.id, ids_detectados)

    def test_fusion_bloquea_distintos_negocios(self):
        """Verifica que no se permita fusionar clientes que pertenecen a negocios diferentes."""
        self._login()

        c_alfa = Cliente(negocio_id=self.negocio.id, nombre='Luis', apellido='Ramos', documento='ALFA1', fecha_nacimiento=date(1990, 1, 1))
        c_beta = Cliente(negocio_id=self.negocio_otro.id, nombre='Luis', apellido='Ramos', documento='BETA1', fecha_nacimiento=date(1990, 1, 1))
        db.session.add_all([c_alfa, c_beta])
        db.session.commit()

        with self.assertRaises(ValueError):
            fusionar_clientes(c_alfa, c_beta)


if __name__ == '__main__':
    unittest.main()
