"""multitenancy: tabla negocios, negocio_id en tablas de dominio, superadmin

- Crea la tabla `negocios` (si no existe) y un negocio por defecto aprobado.
- Añade `negocio_id` a clientes, servicios, transacciones, documentos_cliente,
  notificaciones, productos y movimientos_producto, con backfill al negocio
  por defecto.
- Añade a `users`: negocio_id, is_superadmin, activo. El usuario `admin`
  existente pasa a ser superadmin global (sin negocio).
- La unicidad de clientes.documento y servicios.nombre pasa a ser por negocio.

La migración es DEFENSIVA (idempotente) porque el arranque de la app ejecuta
`db.create_all()` y ALTERs de fallback antes de `flask db upgrade`, así que
parte del esquema puede existir ya. Cada paso comprueba el estado real.

Nota SQLite: las constraints UNIQUE originales de clientes.documento y
servicios.nombre no tienen nombre, así que en SQLite esas dos tablas se
reconstruyen con SQL crudo cuando falta la unique compuesta.

Revision ID: b7f3a21c9d04
Revises: a3af0d638f44
Create Date: 2026-08-04

"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'b7f3a21c9d04'
down_revision = 'a3af0d638f44'
branch_labels = None
depends_on = None

# Tablas de dominio que solo necesitan la columna negocio_id (sin tocar uniques)
TABLAS_TENANT_SIMPLES = ('transacciones', 'documentos_cliente',
                         'notificaciones', 'productos', 'movimientos_producto')
TODAS_TENANT = ('clientes', 'servicios') + TABLAS_TENANT_SIMPLES


def _inspector():
    return inspect(op.get_bind())


def _tiene_columna(tabla, columna):
    return columna in [c['name'] for c in _inspector().get_columns(tabla)]


def _tiene_indice(tabla, nombre):
    return nombre in [i['name'] for i in _inspector().get_indexes(tabla)]


def _add_negocio_id(tabla):
    """Añade negocio_id + FK + índice si faltan (todos los dialectos)."""
    if not _tiene_columna(tabla, 'negocio_id'):
        with op.batch_alter_table(tabla) as batch_op:
            batch_op.add_column(sa.Column('negocio_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                f'fk_{tabla}_negocio', 'negocios', ['negocio_id'], ['id'])
    if not _tiene_indice(tabla, f'ix_{tabla}_negocio_id'):
        op.create_index(f'ix_{tabla}_negocio_id', tabla, ['negocio_id'])


def _rebuild_clientes_sqlite():
    op.execute("""
        CREATE TABLE clientes_new (
            id INTEGER NOT NULL PRIMARY KEY,
            negocio_id INTEGER REFERENCES negocios(id),
            nombre VARCHAR(64) NOT NULL,
            apellido VARCHAR(64) NOT NULL,
            fecha_nacimiento DATE NOT NULL,
            documento VARCHAR(20) NOT NULL,
            tipo_documento VARCHAR(50),
            documento_fecha_emision DATE,
            documento_fecha_vencimiento DATE,
            telefono VARCHAR(20),
            foto_documento VARCHAR(255),
            fecha_registro DATETIME,
            ultima_visita DATETIME,
            CONSTRAINT uq_cliente_negocio_documento UNIQUE (negocio_id, documento)
        )
    """)
    op.execute("""
        INSERT INTO clientes_new (id, negocio_id, nombre, apellido, fecha_nacimiento,
            documento, tipo_documento, documento_fecha_emision, documento_fecha_vencimiento,
            telefono, foto_documento, fecha_registro, ultima_visita)
        SELECT id, COALESCE(negocio_id, 1), nombre, apellido, fecha_nacimiento,
            documento, tipo_documento, documento_fecha_emision, documento_fecha_vencimiento,
            telefono, foto_documento, fecha_registro, ultima_visita
        FROM clientes
    """)
    op.execute('DROP TABLE clientes')
    op.execute('ALTER TABLE clientes_new RENAME TO clientes')
    op.execute('CREATE INDEX IF NOT EXISTS ix_clientes_negocio_id ON clientes (negocio_id)')


def _rebuild_servicios_sqlite():
    op.execute("""
        CREATE TABLE servicios_new (
            id INTEGER NOT NULL PRIMARY KEY,
            negocio_id INTEGER REFERENCES negocios(id),
            nombre VARCHAR(64) NOT NULL,
            descripcion VARCHAR(255),
            comision_porcentaje FLOAT,
            activo BOOLEAN,
            CONSTRAINT uq_servicio_negocio_nombre UNIQUE (negocio_id, nombre)
        )
    """)
    op.execute("""
        INSERT INTO servicios_new (id, negocio_id, nombre, descripcion, comision_porcentaje, activo)
        SELECT id, COALESCE(negocio_id, 1), nombre, descripcion, comision_porcentaje, activo
        FROM servicios
    """)
    op.execute('DROP TABLE servicios')
    op.execute('ALTER TABLE servicios_new RENAME TO servicios')
    op.execute('CREATE INDEX IF NOT EXISTS ix_servicios_negocio_id ON servicios (negocio_id)')


def _tiene_unique_compuesta(tabla, nombre_constraint):
    """Comprueba si ya existe la unique por negocio (por nombre en el DDL/reflection)."""
    for uc in _inspector().get_unique_constraints(tabla):
        if uc.get('name') == nombre_constraint:
            return True
    # En SQLite las uniques pueden reflejarse como índices
    for ix in _inspector().get_indexes(tabla):
        if ix.get('name') == nombre_constraint:
            return True
    return False


def upgrade():
    bind = op.get_bind()
    es_sqlite = bind.dialect.name == 'sqlite'
    inspector = _inspector()

    # 1. Tabla de negocios (puede existir ya por db.create_all)
    if 'negocios' not in inspector.get_table_names():
        op.create_table(
            'negocios',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('nombre', sa.String(120), nullable=False, unique=True),
            sa.Column('slug', sa.String(120), nullable=False, unique=True),
            sa.Column('email_contacto', sa.String(120)),
            sa.Column('telefono', sa.String(30)),
            sa.Column('estado', sa.String(20), nullable=False, server_default='pendiente'),
            sa.Column('notas_admin', sa.Text()),
            sa.Column('created_at', sa.DateTime()),
            sa.Column('aprobado_at', sa.DateTime()),
        )

    # 2. Negocio por defecto para los datos existentes (id=1)
    if not bind.execute(sa.text('SELECT id FROM negocios LIMIT 1')).first():
        ahora = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        op.execute(
            "INSERT INTO negocios (nombre, slug, estado, created_at, aprobado_at) "
            f"VALUES ('Negocio principal', 'negocio-principal', 'aprobado', '{ahora}', '{ahora}')"
        )

    # 3. clientes y servicios: unicidad por negocio (rebuild en SQLite)
    if es_sqlite:
        if not _tiene_columna('clientes', 'negocio_id'):
            op.execute('ALTER TABLE clientes ADD COLUMN negocio_id INTEGER REFERENCES negocios(id)')
        if not _tiene_unique_compuesta('clientes', 'uq_cliente_negocio_documento'):
            _rebuild_clientes_sqlite()
        if not _tiene_columna('servicios', 'negocio_id'):
            op.execute('ALTER TABLE servicios ADD COLUMN negocio_id INTEGER REFERENCES negocios(id)')
        if not _tiene_unique_compuesta('servicios', 'uq_servicio_negocio_nombre'):
            _rebuild_servicios_sqlite()
    else:
        # Nombres de constraint según dialecto (generados por SQLAlchemy)
        if bind.dialect.name == 'mysql':
            uq_clientes, uq_servicios = 'documento', 'nombre'
        else:  # postgresql
            uq_clientes, uq_servicios = 'clientes_documento_key', 'servicios_nombre_key'
        with op.batch_alter_table('clientes') as batch_op:
            if not _tiene_columna('clientes', 'negocio_id'):
                batch_op.add_column(sa.Column('negocio_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'fk_clientes_negocio', 'negocios', ['negocio_id'], ['id'])
            if not _tiene_unique_compuesta('clientes', 'uq_cliente_negocio_documento'):
                nombres_uniques_cli = [u.get('name') for u in _inspector().get_unique_constraints('clientes')]
                if uq_clientes in nombres_uniques_cli:
                    batch_op.drop_constraint(uq_clientes, type_='unique')
                batch_op.create_unique_constraint(
                    'uq_cliente_negocio_documento', ['negocio_id', 'documento'])
        with op.batch_alter_table('servicios') as batch_op:
            if not _tiene_columna('servicios', 'negocio_id'):
                batch_op.add_column(sa.Column('negocio_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'fk_servicios_negocio', 'negocios', ['negocio_id'], ['id'])
            if not _tiene_unique_compuesta('servicios', 'uq_servicio_negocio_nombre'):
                nombres_uniques_srv = [u.get('name') for u in _inspector().get_unique_constraints('servicios')]
                if uq_servicios in nombres_uniques_srv:
                    batch_op.drop_constraint(uq_servicios, type_='unique')
                batch_op.create_unique_constraint(
                    'uq_servicio_negocio_nombre', ['negocio_id', 'nombre'])
        if not _tiene_indice('clientes', 'ix_clientes_negocio_id'):
            op.create_index('ix_clientes_negocio_id', 'clientes', ['negocio_id'])
        if not _tiene_indice('servicios', 'ix_servicios_negocio_id'):
            op.create_index('ix_servicios_negocio_id', 'servicios', ['negocio_id'])

    op.execute('UPDATE clientes SET negocio_id = 1 WHERE negocio_id IS NULL')
    op.execute('UPDATE servicios SET negocio_id = 1 WHERE negocio_id IS NULL')

    # 4. Resto de tablas de dominio: solo columna + backfill
    for tabla in TABLAS_TENANT_SIMPLES:
        _add_negocio_id(tabla)
        op.execute(f'UPDATE {tabla} SET negocio_id = 1 WHERE negocio_id IS NULL')

    # 5. Campos nuevos en users
    with op.batch_alter_table('users') as batch_op:
        if not _tiene_columna('users', 'negocio_id'):
            batch_op.add_column(sa.Column('negocio_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_users_negocio', 'negocios', ['negocio_id'], ['id'])
        if not _tiene_columna('users', 'is_superadmin'):
            batch_op.add_column(sa.Column('is_superadmin', sa.Boolean(),
                                          nullable=False, server_default=sa.false()))
        if not _tiene_columna('users', 'activo'):
            batch_op.add_column(sa.Column('activo', sa.Boolean(),
                                          nullable=False, server_default=sa.true()))

    # 6. Usuarios existentes -> negocio por defecto; admin -> superadmin global
    op.execute("UPDATE users SET negocio_id = 1 WHERE negocio_id IS NULL AND username != 'admin'")
    op.execute("UPDATE users SET is_superadmin = TRUE, negocio_id = NULL, is_admin = TRUE "
               "WHERE username = 'admin'")


def downgrade():
    bind = op.get_bind()
    es_sqlite = bind.dialect.name == 'sqlite'

    with op.batch_alter_table('users') as batch_op:
        if _tiene_columna('users', 'negocio_id'):
            batch_op.drop_constraint('fk_users_negocio', type_='foreignkey')
            batch_op.drop_column('negocio_id')
        if _tiene_columna('users', 'is_superadmin'):
            batch_op.drop_column('is_superadmin')
        if _tiene_columna('users', 'activo'):
            batch_op.drop_column('activo')

    for tabla in TABLAS_TENANT_SIMPLES:
        with op.batch_alter_table(tabla) as batch_op:
            if _tiene_indice(tabla, f'ix_{tabla}_negocio_id'):
                batch_op.drop_index(f'ix_{tabla}_negocio_id')
            if _tiene_columna(tabla, 'negocio_id'):
                batch_op.drop_constraint(f'fk_{tabla}_negocio', type_='foreignkey')
                batch_op.drop_column('negocio_id')

    # En SQLite el downgrade de clientes/servicios requeriría otro rebuild;
    # se omite: usar una copia de seguridad de la BD si hay que volver atrás.
    if not es_sqlite:
        if bind.dialect.name == 'mysql':
            uq_clientes, uq_servicios = 'documento', 'nombre'
        else:
            uq_clientes, uq_servicios = 'clientes_documento_key', 'servicios_nombre_key'
        with op.batch_alter_table('servicios') as batch_op:
            batch_op.drop_index('ix_servicios_negocio_id')
            batch_op.drop_constraint('fk_servicios_negocio', type_='foreignkey')
            batch_op.drop_constraint('uq_servicio_negocio_nombre', type_='unique')
            batch_op.create_unique_constraint(uq_servicios, ['nombre'])
            batch_op.drop_column('negocio_id')
        with op.batch_alter_table('clientes') as batch_op:
            batch_op.drop_index('ix_clientes_negocio_id')
            batch_op.drop_constraint('fk_clientes_negocio', type_='foreignkey')
            batch_op.drop_constraint('uq_cliente_negocio_documento', type_='unique')
            batch_op.create_unique_constraint(uq_clientes, ['documento'])
            batch_op.drop_column('negocio_id')

    op.drop_table('negocios')
