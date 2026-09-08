import unittest
from datetime import datetime, date, timedelta
from app import create_app
from app.extensions import db
from app.models.negocio import Negocio
from app.models.user import User
from app.models.cliente import Cliente, Servicio
from app.models.transaccion import Transaccion
from app.models.documento import DocumentoCliente
from app.utils.parse_recibo import parsear_recibo


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = 'db/test_uploads'


class ExtensionApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

        db.create_all()

        # Crear negocio y usuario
        self.negocio = Negocio(nombre="Agencia Centro", slug="agencia-centro", estado="aprobado")
        db.session.add(self.negocio)
        db.session.commit()

        self.user = User(
            username="operador_ext",
            email="operador@ext.com",
            is_admin=False,
            activo=True,
            negocio_id=self.negocio.id
        )
        self.user.set_password("pass123")
        db.session.add(self.user)

        self.servicio_wu = Servicio(
            nombre="Western Union",
            comision_porcentaje=5.0,
            negocio_id=self.negocio.id
        )
        db.session.add(self.servicio_wu)

        # Cliente 1: con saldo disponible
        self.cliente_activo = Cliente(
            nombre="MARIO",
            apellido="ROSSI",
            fecha_nacimiento=date(1990, 5, 15),
            tipo_documento="DNI",
            documento="Y1234567A",
            telefono="34600112233",
            negocio_id=self.negocio.id
        )
        db.session.add(self.cliente_activo)

        # Cliente 2: con límite agotado
        self.cliente_limite = Cliente(
            nombre="GIUSEPPE",
            apellido="VERDI",
            fecha_nacimiento=date(1985, 8, 20),
            tipo_documento="NIE",
            documento="X9876543Z",
            telefono="393401122334",
            negocio_id=self.negocio.id
        )
        db.session.add(self.cliente_limite)
        db.session.commit()

        # Agregar documento adicional al cliente 1
        self.doc_sec = DocumentoCliente(
            cliente_id=self.cliente_activo.id,
            tipo_documento="PASAPORTE",
            numero_documento="PASS-RO-999",
            fecha_vencimiento=date.today() + timedelta(days=180),
            estado="vigente",
            es_documento_principal=False,
            negocio_id=self.negocio.id
        )
        db.session.add(self.doc_sec)

        # Agregar transacción grande al cliente 2 para copar su límite semanal
        self.tx_limite = Transaccion(
            cliente_id=self.cliente_limite.id,
            servicio_id=self.servicio_wu.id,
            monto=1000.0,
            comision=50.0,
            fecha=datetime.utcnow() - timedelta(days=2),
            negocio_id=self.negocio.id
        )
        db.session.add(self.tx_limite)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self):
        return self.client.post('/login', data={
            'username': 'operador_ext',
            'password': 'pass123'
        }, follow_redirects=True)

    def test_parsear_recibo_mtcn_western_union(self):
        """Verifica que se extraiga el MTCN de un recibo Western Union."""
        recibo = """
        WESTERN UNION MONEY TRANSFER
        MITTENTE: MARIO ROSSI
        DOCUMENTO: Y1234567A
        MTCN: 987-654-3210
        IMPORTO INVIATO: 250,00 EUR
        COMMISSIONE: 12,50 EUR
        """
        datos = parsear_recibo(recibo)
        self.assertEqual(datos.get('nombre'), 'MARIO')
        self.assertEqual(datos.get('apellido'), 'ROSSI')
        self.assertEqual(datos.get('referencia'), '9876543210')
        self.assertEqual(datos.get('monto'), 250.0)

    def test_parsear_recibo_pin_ria(self):
        """Verifica que se extraiga el PIN, remitente y documento de orden de Ria."""
        recibo = """
        RIA MONEY TRANSFER
        ORDER PIN: 123456789
        SENDER: GIUSEPPE VERDI
        DOCUMENT: X9876543Z
        AMOUNT: 300.00 EUR
        """
        datos = parsear_recibo(recibo)
        self.assertEqual(datos.get('referencia'), '123456789')
        self.assertEqual(datos.get('monto'), 300.0)
        self.assertEqual(datos.get('nombre'), 'GIUSEPPE')
        self.assertEqual(datos.get('apellido'), 'VERDI')
        self.assertEqual(datos.get('documento'), 'X9876543Z')
        self.assertEqual(datos.get('servicio_hint'), 'Ria Money Transfer')

    def test_parsear_recibo_ria_multilinea_tabla(self):
        """Verifica extracción cuando las etiquetas y valores están en líneas separadas (tablas web)."""
        recibo = """
        Ria Money Transfer
        Ricevuta di Trasferimento
        
        DATI DEL MITTENTE
        Nome e cognome
        MARCO AURELIO
        Numero documento
        Passaporto YA5544332
        Telefono
        +39 345 6789012
        
        DATI DEL BENEFICIARIO
        Nome e cognome
        MARIA CONCEPCION
        Paese
        COLOMBIA
        
        DETTAGLI DEL PAGAMENTO
        PIN
        56399431
        Importo
        850,00 EUR
        Totale
        878,05 EUR
        """
        datos = parsear_recibo(recibo)
        self.assertEqual(datos.get('nombre'), 'MARCO')
        self.assertEqual(datos.get('apellido'), 'AURELIO')
        self.assertEqual(datos.get('documento'), 'YA5544332')
        self.assertEqual(datos.get('telefono'), '+393456789012')
        self.assertEqual(datos.get('referencia'), '56399431')
        self.assertEqual(datos.get('monto'), 878.05)
        self.assertEqual(datos.get('servicio_hint'), 'Ria Money Transfer')

    def test_parsear_recibo_mondial_bony_evita_falso_positivo_ria(self):
        """Verifica que un recibo de Mondial Bony con palabras bancarias italianas devuelva Mondial y no Ria."""
        recibo = """
        RICEVITORIA AUTORIZZATA - OPERAZIONE BANCARIA E FINANZIARIA
        MONDIAL BONY SERVICE
        RICEVUTA DI TRASFERIMENTO FONDI
        
        DATI DEL MITTENTE:
        NOME: SOULEYMANE
        COGNOME: DIALLO
        DOCUMENTO: Y7654321B
        TELEFONO: +39 333 9988776
        
        DETTAGLI TRANSAZIONE:
        CODICE TRANSAZIONE: MB987654321
        TOTALE PAGATO: 420,00 EUR
        """
        datos = parsear_recibo(recibo)
        self.assertEqual(datos.get('servicio_hint'), 'Mondial')
        self.assertEqual(datos.get('nombre'), 'SOULEYMANE')
        self.assertEqual(datos.get('apellido'), 'DIALLO')
        self.assertEqual(datos.get('documento'), 'Y7654321B')
        self.assertEqual(datos.get('telefono'), '+393339988776')
        self.assertEqual(datos.get('referencia'), 'MB987654321')
        self.assertEqual(datos.get('monto'), 420.0)

    def test_parsear_recibo_western_union_wupos_print(self):
        """Verifica que un recibo de impresión WUPOS devuelva Western Union y extraiga MTCN y monto."""
        recibo = """
        WUPOS 2.0 - RECEIPT PRINT
        WESTERN UNION FINANCIAL SERVICES
        MTCN: 123 456 7890
        SENDER: ALBERTO GOMEZ
        DOCUMENT NUMBER: X1122334A
        TOTAL AMOUNT: 550,00 EUR
        """
        datos = parsear_recibo(recibo)
        self.assertEqual(datos.get('servicio_hint'), 'Western Union')
        self.assertEqual(datos.get('nombre'), 'ALBERTO')
        self.assertEqual(datos.get('apellido'), 'GOMEZ')
        self.assertEqual(datos.get('referencia'), '1234567890')
        self.assertEqual(datos.get('monto'), 550.0)

    def test_api_analizar_recibo_endpoint(self):
        """Verifica que el endpoint /transacciones/api/analizar-recibo devuelva los datos analizados."""
        self._login()
        recibo = """
        MONEYGRAM INTERNATIONAL
        MITTENTE: CARLOS GOMEZ
        REFERENCE NUMBER: 88776655
        IMPORTO: 450,00 EUR
        """
        resp = self.client.post('/transacciones/api/analizar-recibo', json={'texto': recibo})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get('referencia'), '88776655')
        self.assertEqual(data.get('monto'), 450.0)

    def test_api_verificar_cliente_disponible(self):
        """Verifica que /transacciones/api/verificar-cliente devuelva saldo disponible y estado."""
        self._login()
        resp = self.client.get('/transacciones/api/verificar-cliente?q=MARIO')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        clientes = data.get('clientes', [])
        self.assertTrue(len(clientes) >= 1)
        c = clientes[0]
        self.assertEqual(c['nombre'], 'MARIO')
        self.assertTrue(c['saldo_disponible'] > 0)
        self.assertTrue(c['puede_enviar'])

        # Debe incluir el documento secundario
        docs_adicionales = c.get('documentos_adicionales', [])
        self.assertTrue(any(d['numero'] == 'PASS-RO-999' for d in docs_adicionales))

    def test_api_verificar_cliente_por_documento_secundario(self):
        """Verifica que la búsqueda encuentre al cliente ingresando el número de su documento secundario."""
        self._login()
        resp = self.client.get('/transacciones/api/verificar-cliente?q=PASS-RO-999')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        clientes = data.get('clientes', [])
        self.assertEqual(len(clientes), 1)
        self.assertEqual(clientes[0]['nombre'], 'MARIO')

    def test_api_verificar_cliente_limite_alcanzado(self):
        """Verifica que un cliente con límite semanal consumido retorne saldo 0 y no apto para enviar."""
        self._login()
        resp = self.client.get('/transacciones/api/verificar-cliente?q=GIUSEPPE')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        clientes = data.get('clientes', [])
        self.assertEqual(len(clientes), 1)
        c = clientes[0]
        self.assertEqual(c['saldo_disponible'], 0.0)
        self.assertFalse(c['puede_enviar'])
    def test_api_negocio_info(self):
        """Verifica que el endpoint /transacciones/api/negocio-info retorne los datos del negocio."""
        # Sin login
        resp_anon = self.client.get('/transacciones/api/negocio-info')
        self.assertEqual(resp_anon.status_code, 401)

        # Con login
        self._login()
        resp = self.client.get('/transacciones/api/negocio-info')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('ok'))
        self.assertEqual(data['negocio']['id'], self.negocio.id)
        self.assertEqual(data['negocio']['slug'], self.negocio.slug)

    def test_registro_rapido_get_ok(self):
        """Verifica que GET /transacciones/registro-rapido cargue correctamente (status 200)."""
        self._login()
        resp = self.client.get('/transacciones/registro-rapido')
        self.assertEqual(resp.status_code, 200)

    def test_transacciones_lista_con_cliente_nulo(self):
        """Verifica que /transacciones/ no falle con error 500 si hay transacciones con cliente nulo."""
        self._login()
        tx_huerfana = Transaccion(
            cliente_id=None,
            servicio_id=self.servicio_wu.id,
            monto=40.0,
            comision=2.0,
            negocio_id=self.negocio.id
        )
        db.session.add(tx_huerfana)
        db.session.commit()

        resp = self.client.get('/transacciones/')
        self.assertEqual(resp.status_code, 200)


if __name__ == '__main__':
    unittest.main()
