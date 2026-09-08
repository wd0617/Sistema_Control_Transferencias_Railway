"""agregar modulo caja: caja_sesiones y movimientos_caja

Revision ID: c1f8a7e2b345
Revises: b7f3a21c9d04
Create Date: 2026-09-08 15:30:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = 'c1f8a7e2b345'
down_revision = 'b7f3a21c9d04'
branch_labels = None
depends_on = None


def _inspector():
    return inspect(op.get_bind())


def upgrade():
    inspector = _inspector()
    tablas = inspector.get_table_names()

    # 1. Tabla caja_sesiones
    if 'caja_sesiones' not in tablas:
        op.create_table(
            'caja_sesiones',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('negocio_id', sa.Integer(), sa.ForeignKey('negocios.id'), nullable=False),
            sa.Column('usuario_apertura_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('usuario_cierre_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('fecha_apertura', sa.DateTime(), nullable=False),
            sa.Column('fecha_cierre', sa.DateTime(), nullable=True),
            sa.Column('estado', sa.String(20), nullable=False, server_default='abierta'),
            sa.Column('monto_inicial', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('monto_esperado', sa.Float(), nullable=True),
            sa.Column('monto_real', sa.Float(), nullable=True),
            sa.Column('diferencia', sa.Float(), nullable=True),
            sa.Column('notas_apertura', sa.Text(), nullable=True),
            sa.Column('notas_cierre', sa.Text(), nullable=True),
        )
        op.create_index('ix_caja_sesiones_negocio_id', 'caja_sesiones', ['negocio_id'])

    # 2. Tabla movimientos_caja
    if 'movimientos_caja' not in tablas:
        op.create_table(
            'movimientos_caja',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('negocio_id', sa.Integer(), sa.ForeignKey('negocios.id'), nullable=False),
            sa.Column('caja_sesion_id', sa.Integer(), sa.ForeignKey('caja_sesiones.id'), nullable=False),
            sa.Column('tipo', sa.String(20), nullable=False),
            sa.Column('concepto', sa.String(200), nullable=False),
            sa.Column('monto', sa.Float(), nullable=False),
            sa.Column('fecha', sa.DateTime(), nullable=False),
            sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        )
        op.create_index('ix_movimientos_caja_negocio_id', 'movimientos_caja', ['negocio_id'])


def downgrade():
    inspector = _inspector()
    tablas = inspector.get_table_names()

    if 'movimientos_caja' in tablas:
        op.drop_index('ix_movimientos_caja_negocio_id', table_name='movimientos_caja')
        op.drop_table('movimientos_caja')

    if 'caja_sesiones' in tablas:
        op.drop_index('ix_caja_sesiones_negocio_id', table_name='caja_sesiones')
        op.drop_table('caja_sesiones')
