"""
Utilidades para generar notificaciones automáticas del sistema.
"""

from datetime import datetime, timedelta, date
from sqlalchemy import func
from app.extensions import db
from app.models.cliente import Cliente
from app.models.transaccion import Transaccion, Notificacion
from app.models.documento import DocumentoCliente

def generar_notificaciones():
    """
    Genera notificaciones automáticas para:
    - Clientes cerca del límite semanal (< 100€ disponibles)
    - Documentos por vencer (<= 30 días)
    - Documentos vencidos
    
    Evita duplicados creando notificaciones solo si no existe una similar reciente.
    """
    limite = 999
    dias_alerta = 30
    fecha_inicio = datetime.utcnow() - timedelta(days=7)
    
    # 1. Notificaciones de clientes cerca del límite
    clientes_con_gastos = db.session.query(
        Transaccion.cliente_id,
        func.sum(Transaccion.monto).label('total_gastado')
    ).filter(
        Transaccion.fecha >= fecha_inicio
    ).group_by(
        Transaccion.cliente_id
    ).having(
        func.sum(Transaccion.monto) > (limite - 100)
    ).all()
    
    for row in clientes_con_gastos:
        saldo = limite - float(row.total_gastado)
        _crear_notificacion_si_no_existe(
            cliente_id=row.cliente_id,
            tipo='alerta_limite',
            mensaje=f'El cliente está cerca del límite semanal ({saldo:.0f}€ de {limite}€ disponibles)'
        )
    
    # 2. Notificaciones de documentos por vencer
    fecha_limite = date.today() + timedelta(days=dias_alerta)
    docs_por_vencer = DocumentoCliente.query.filter(
        DocumentoCliente.fecha_vencimiento <= fecha_limite,
        DocumentoCliente.fecha_vencimiento >= date.today()
    ).all()
    
    for doc in docs_por_vencer:
        dias = (doc.fecha_vencimiento - date.today()).days
        _crear_notificacion_si_no_existe(
            cliente_id=doc.cliente_id,
            tipo='documento_por_vencer',
            mensaje=f'El documento {doc.tipo_documento} ({doc.numero_documento}) vence en {dias} días'
        )
    
    # 3. Notificaciones de documentos vencidos
    docs_vencidos = DocumentoCliente.query.filter(
        DocumentoCliente.fecha_vencimiento < date.today()
    ).all()
    
    for doc in docs_vencidos:
        dias = (date.today() - doc.fecha_vencimiento).days
        _crear_notificacion_si_no_existe(
            cliente_id=doc.cliente_id,
            tipo='documento_vencido',
            mensaje=f'El documento {doc.tipo_documento} ({doc.numero_documento}) venció hace {dias} días'
        )

def _crear_notificacion_si_no_existe(cliente_id, tipo, mensaje):
    """Crea una notificación solo si no existe una del mismo tipo creada en las últimas 24h."""
    desde = datetime.utcnow() - timedelta(hours=24)
    
    # Verificar si ya existe una notificación del mismo tipo para este cliente
    # creada en las últimas 24h (leída o no), para evitar regenerar alertas
    # inmediatamente después de que el usuario las marque como leídas.
    existente = Notificacion.query.filter(
        Notificacion.cliente_id == cliente_id,
        Notificacion.tipo == tipo,
        Notificacion.fecha_creacion >= desde
    ).first()
    
    if not existente:
        notif = Notificacion(
            cliente_id=cliente_id,
            tipo=tipo,
            mensaje=mensaje,
            leida=False,
            fecha_creacion=datetime.utcnow()
        )
        db.session.add(notif)
        db.session.commit()

def contar_notificaciones_pendientes():
    """Retorna el número de notificaciones no leídas."""
    return Notificacion.query.filter_by(leida=False).count()

def obtener_notificaciones_pendientes(limit=10):
    """Retorna las notificaciones no leídas más recientes."""
    return Notificacion.query.filter_by(leida=False).order_by(
        Notificacion.fecha_creacion.desc()
    ).limit(limit).all()
