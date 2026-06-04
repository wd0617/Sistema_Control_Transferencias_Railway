import os
import sys
from datetime import datetime, timedelta, date
from werkzeug.security import generate_password_hash
from app import create_app, db
from app.models.user import User
from app.models.cliente import Cliente, Servicio
from app.models.transaccion import Transaccion, Notificacion
from app.models.documento import DocumentoCliente

app = create_app()

def crear_estructura():
    """Crea la estructura de la base de datos"""
    with app.app_context():
        db.create_all()
        print("Base de datos creada correctamente")

def poblar_datos_prueba():
    """Añade datos de prueba a la base de datos"""
    with app.app_context():
        # Comprobar si ya existen datos
        if User.query.first():
            print("La base de datos ya tiene datos, omitiendo la inicialización")
            return
            
        # Crear usuario administrador
        admin = User(
            username='admin',
            email='admin@sistema.com',
            nombre='Administrador',
            apellido='Sistema',
            is_admin=True
        )
        admin.set_password('admin123')
        
        # Crear usuario normal
        user = User(
            username='usuario',
            email='usuario@sistema.com',
            nombre='Usuario',
            apellido='Normal'
        )
        user.set_password('usuario123')
        
        db.session.add_all([admin, user])
        
        # Crear servicios de transferencia
        servicios = [
            Servicio(nombre='Western Union', descripcion='Transferencias internacionales', comision_porcentaje=3.5),
            Servicio(nombre='Mondial', descripcion='Transferencias rápidas', comision_porcentaje=2.8),
            Servicio(nombre='Monty', descripcion='Transferencias digitales', comision_porcentaje=2.0),
            Servicio(nombre='Moneygram', descripcion='Transferencias globales', comision_porcentaje=3.2),
            Servicio(nombre='Ria', descripcion='Transferencias a bajo costo', comision_porcentaje=2.5)
        ]
        db.session.add_all(servicios)
        
        # Crear clientes de ejemplo
        clientes = [
            Cliente(
                nombre='Juan', 
                apellido='Gómez', 
                fecha_nacimiento=datetime(1985, 5, 12),
                documento='X1234567A',
                telefono='612345678',
                foto_documento='juan_gomez.jpg'
            ),
            Cliente(
                nombre='María', 
                apellido='López', 
                fecha_nacimiento=datetime(1990, 8, 23),
                documento='Y7654321B',
                telefono='623456789',
                foto_documento='maria_lopez.jpg'
            ),
            Cliente(
                nombre='Pedro', 
                apellido='Sánchez', 
                fecha_nacimiento=datetime(1978, 2, 15),
                documento='Z9876543C',
                telefono='634567890',
                foto_documento='pedro_sanchez.jpg'
            ),
            Cliente(
                nombre='Ana', 
                apellido='Martínez', 
                fecha_nacimiento=datetime(1995, 11, 30),
                documento='A1357924D',
                telefono='645678901',
                foto_documento='ana_martinez.jpg'
            ),
            Cliente(
                nombre='Carlos', 
                apellido='Ruiz', 
                fecha_nacimiento=datetime(1980, 7, 7),
                documento='B2468135E',
                telefono='656789012',
                foto_documento='carlos_ruiz.jpg'
            )
        ]
        
        # Asignar servicios aleatorios a cada cliente
        import random
        for cliente in clientes:
            # Asignar entre 1 y 3 servicios aleatorios a cada cliente
            servicios_asignados = random.sample(servicios, random.randint(1, 3))
            cliente.servicios.extend(servicios_asignados)
        
        db.session.add_all(clientes)
        
        # Crear transacciones de ejemplo
        now = datetime.utcnow()
        transacciones = []
        
        # Transacciones para el cliente 1 (Juan Gómez) - Al límite de su capacidad
        for i in range(5):
            fecha = now - timedelta(days=i)
            transacciones.append(
                Transaccion(
                    cliente_id=1,
                    servicio_id=1,  # Western Union
                    monto=180,  # Total: 900€
                    comision=180 * 0.035,
                    fecha=fecha,
                    referencia=f'REF-WU-{10000+i}',
                    notas='Envío familiar',
                    creado_por=1  # admin
                )
            )
        
        # Transacciones para cliente 2 (María López) - Algunas transacciones
        for i in range(2):
            fecha = now - timedelta(days=i*2)
            transacciones.append(
                Transaccion(
                    cliente_id=2,
                    servicio_id=2,  # Mondial
                    monto=250,
                    comision=250 * 0.028,
                    fecha=fecha,
                    referencia=f'REF-MD-{20000+i}',
                    notas='Envío mensual',
                    creado_por=2  # usuario normal
                )
            )
        
        # Transacciones para cliente 3 (Pedro Sánchez) - Una sola transacción reciente
        transacciones.append(
            Transaccion(
                cliente_id=3,
                servicio_id=3,  # Monty
                monto=500,
                comision=500 * 0.02,
                fecha=now - timedelta(hours=2),
                referencia='REF-MT-30001',
                notas='Envío urgente',
                creado_por=1  # admin
            )
        )
        
        # Transacciones antiguas para cliente 4 (Ana Martínez)
        for i in range(3):
            fecha = now - timedelta(days=10+i)
            transacciones.append(
                Transaccion(
                    cliente_id=4,
                    servicio_id=4,  # Moneygram
                    monto=150,
                    comision=150 * 0.032,
                    fecha=fecha,
                    referencia=f'REF-MG-{40000+i}',
                    notas='Envío periódico',
                    creado_por=2  # usuario normal
                )
            )
        
        # Cliente 5 (Carlos Ruiz) sin transacciones
        
        db.session.add_all(transacciones)
        
        # Crear algunas notificaciones
        notificaciones = [
            Notificacion(
                cliente_id=1,
                tipo='alerta_limite',
                mensaje='El cliente está cerca del límite semanal de transferencias (900€ de 999€)',
                fecha_creacion=now - timedelta(hours=6)
            ),
            Notificacion(
                cliente_id=4,
                tipo='puede_enviar',
                mensaje='El cliente Ana Martínez ahora puede realizar nuevos envíos (límite restablecido)',
                fecha_creacion=now - timedelta(days=1)
            )
        ]
        
        db.session.add_all(notificaciones)
        
        # Crear documentos de ejemplo para los clientes
        documentos = [
            # Cliente 1 (Juan Gómez) - Documento vencido
            DocumentoCliente(
                cliente_id=1,
                tipo_documento='NIE',
                numero_documento='X1234567A',
                pais_emision='España',
                fecha_emision=datetime(2018, 1, 15).date(),
                fecha_vencimiento=datetime(2023, 1, 15).date(),  # Vencido
                es_documento_principal=True,
                estado='vencido',
                fecha_registro=now - timedelta(days=200),
                actualizado_por=1
            ),
            # Cliente 2 (María López) - Por vencer
            DocumentoCliente(
                cliente_id=2,
                tipo_documento='PASAPORTE',
                numero_documento='ABC123456',
                pais_emision='España',
                fecha_emision=datetime(2022, 3, 10).date(),
                fecha_vencimiento=date.today() + timedelta(days=20),  # Vence pronto
                es_documento_principal=True,
                estado='por_vencer',
                fecha_registro=now - timedelta(days=100),
                actualizado_por=1
            ),
            # Cliente 3 (Pedro Sánchez) - Vigente
            DocumentoCliente(
                cliente_id=3,
                tipo_documento='DNI',
                numero_documento='12345678Z',
                pais_emision='España',
                fecha_emision=datetime(2023, 6, 1).date(),
                fecha_vencimiento=datetime(2033, 6, 1).date(),  # Vigente
                es_documento_principal=True,
                estado='vigente',
                fecha_registro=now - timedelta(days=50),
                actualizado_por=1
            ),
            # Cliente 4 (Ana Martínez) - Documento secundario
            DocumentoCliente(
                cliente_id=4,
                tipo_documento='PERMISO_RESIDENCIA',
                numero_documento='RES-987654',
                pais_emision='España',
                fecha_emision=datetime(2022, 1, 1).date(),
                fecha_vencimiento=datetime(2027, 1, 1).date(),
                es_documento_principal=True,
                estado='vigente',
                fecha_registro=now - timedelta(days=30),
                actualizado_por=2
            ),
        ]
        
        db.session.add_all(documentos)
        
        # Guardar todos los cambios
        db.session.commit()
        
        print("Base de datos inicializada con datos de prueba")
        print(f"- {len([admin, user])} usuarios")
        print(f"- {len(servicios)} servicios")
        print(f"- {len(clientes)} clientes")
        print(f"- {len(transacciones)} transacciones")
        print(f"- {len(documentos)} documentos")
        print(f"- {len(notificaciones)} notificaciones")

if __name__ == '__main__':
    crear_estructura()
    poblar_datos_prueba()
