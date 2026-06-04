from flask import Blueprint, render_template, redirect, url_for, current_app
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from app.models.cliente import Cliente, Servicio
from app.models.transaccion import Transaccion
from sqlalchemy import func, and_
from app.extensions import db

main = Blueprint('main', __name__)

# Función auxiliar para manejar fechas de forma segura
def safe_strftime(fecha_obj, formato='%Y-%m-%d'):
    """Convierte una fecha a string de forma segura.
    Si fecha_obj ya es string, lo devuelve tal cual.
    Si es un objeto datetime o date, aplica strftime con el formato indicado."""
    if isinstance(fecha_obj, str):
        return fecha_obj
    elif isinstance(fecha_obj, (datetime, date)):
        return fecha_obj.strftime(formato)
    return str(fecha_obj)  # En caso de otro tipo, convertir a string

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html', now=datetime.now())

@main.route('/dashboard')
@login_required
def dashboard():
    # Obtener conteo total de clientes
    clientes_count = Cliente.query.count()
    
    # Obtener transacciones realizadas hoy
    hoy = date.today()
    transacciones_hoy = Transaccion.query.filter(
        func.date(Transaccion.fecha) == hoy
    ).count()
    
    # Calcular clientes cercanos al límite en una sola query SQL
    limite = current_app.config.get('LIMITE_TRANSFERENCIA_SEMANAL', 999)
    fecha_inicio = datetime.utcnow() - timedelta(days=7)
    
    # Subquery: clientes cuya suma de transacciones semanal > limite - 100
    clientes_con_gastos = db.session.query(
        Transaccion.cliente_id,
        func.sum(Transaccion.monto).label('total_gastado')
    ).filter(
        Transaccion.fecha >= fecha_inicio
    ).group_by(
        Transaccion.cliente_id
    ).having(
        func.sum(Transaccion.monto) > (limite - 100)
    ).subquery()
    
    clientes_limite = db.session.query(func.count(Cliente.id)).filter(
        Cliente.id.in_(db.session.query(clientes_con_gastos.c.cliente_id))
    ).scalar() or 0
    
    # Obtener clientes recientes (últimos 5 con actividad)
    clientes_recientes = Cliente.query.order_by(Cliente.ultima_visita.desc()).limit(5).all()
    
    # Precalcular saldos de clientes recientes en una sola query
    saldos = {}
    if clientes_recientes:
        recientes_ids = [c.id for c in clientes_recientes]
        resultados = db.session.query(
            Transaccion.cliente_id,
            func.sum(Transaccion.monto).label('total')
        ).filter(
            Transaccion.cliente_id.in_(recientes_ids),
            Transaccion.fecha >= fecha_inicio
        ).group_by(Transaccion.cliente_id).all()
        
        sumas = {r.cliente_id: float(r.total or 0) for r in resultados}
        saldos = {cid: limite - sumas.get(cid, 0) for cid in recientes_ids}
    
    # Obtener servicios disponibles
    servicios = Servicio.query.all()
    
    # Estadísticas de documentos
    from app.models.documento import DocumentoCliente
    try:
        stats_docs = DocumentoCliente.contar_por_estado()
        docs_vencidos = stats_docs.get('vencidos', 0)
        docs_por_vencer = stats_docs.get('por_vencer', 0)
    except:
        docs_vencidos = 0
        docs_por_vencer = 0
    
    # En una versión futura, se pueden implementar notificaciones
    notificaciones = []
    
    return render_template('dashboard.html', 
                          now=datetime.now(),
                          clientes_count=clientes_count,
                          transacciones_hoy=transacciones_hoy,
                          clientes_limite=clientes_limite,
                          clientes_recientes=clientes_recientes,
                          saldos=saldos,
                          servicios=servicios,
                          notificaciones=notificaciones,
                          docs_vencidos=docs_vencidos,
                          docs_por_vencer=docs_por_vencer)

