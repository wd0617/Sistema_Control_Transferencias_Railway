from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.caja import CajaSesion, MovimientoCaja
from app.models.transaccion import Transaccion
from app.models.producto import MovimientoProducto
from app.utils.tenancy import query_negocio, get_negocio_o_404

caja = Blueprint('caja', __name__)


@caja.route('/')
@login_required
def index():
    """Tablero principal de caja."""
    caja_activa = query_negocio(CajaSesion).filter_by(estado='abierta')\
        .order_by(CajaSesion.fecha_apertura.desc()).first()

    if caja_activa:
        resumen = caja_activa.calcular_resumen()
        movimientos = caja_activa.movimientos.order_by(MovimientoCaja.fecha.desc()).all()
        
        # Últimas transferencias de este turno
        transacciones = query_negocio(Transaccion)\
            .filter(Transaccion.fecha >= caja_activa.fecha_apertura)\
            .order_by(Transaccion.fecha.desc()).limit(15).all()

        # Últimas ventas de productos de este turno
        ventas = query_negocio(MovimientoProducto)\
            .filter(MovimientoProducto.tipo == 'venta', MovimientoProducto.fecha >= caja_activa.fecha_apertura)\
            .order_by(MovimientoProducto.fecha.desc()).limit(15).all()

        return render_template(
            'caja/index.html',
            caja_activa=caja_activa,
            resumen=resumen,
            movimientos=movimientos,
            transacciones=transacciones,
            ventas=ventas
        )

    # Si no hay caja abierta, consultar la última cerrada para sugerir fondo inicial
    ultima_caja = query_negocio(CajaSesion).filter_by(estado='cerrada')\
        .order_by(CajaSesion.fecha_cierre.desc()).first()

    return render_template('caja/index.html', caja_activa=None, ultima_caja=ultima_caja)


@caja.route('/abrir', methods=['POST'])
@login_required
def abrir():
    """Abre una nueva sesión de caja."""
    existente = query_negocio(CajaSesion).filter_by(estado='abierta').first()
    if existente:
        flash('Ya existe una caja abierta para este negocio.', 'warning')
        return redirect(url_for('caja.index'))

    try:
        monto_raw = request.form.get('monto_inicial', '0').replace(',', '.').strip()
        monto_inicial = float(monto_raw) if monto_raw else 0.0
    except ValueError:
        flash('El monto inicial introducido no es válido.', 'danger')
        return redirect(url_for('caja.index'))

    if monto_inicial < 0:
        flash('El monto inicial no puede ser negativo.', 'danger')
        return redirect(url_for('caja.index'))

    notas = request.form.get('notas_apertura', '').strip()

    nueva_caja = CajaSesion(
        usuario_apertura_id=current_user.id,
        monto_inicial=monto_inicial,
        notas_apertura=notas or None,
        estado='abierta'
    )
    db.session.add(nueva_caja)
    db.session.commit()

    flash(f'Caja abierta correctamente con un fondo inicial de {monto_inicial:,.2f} €.', 'success')
    return redirect(url_for('caja.index'))


@caja.route('/movimiento', methods=['POST'])
@login_required
def movimiento():
    """Registra una entrada o salida manual de efectivo en la caja activa."""
    caja_activa = query_negocio(CajaSesion).filter_by(estado='abierta').first()
    if not caja_activa:
        flash('No hay ninguna caja abierta para registrar movimientos.', 'danger')
        return redirect(url_for('caja.index'))

    tipo = request.form.get('tipo', '').strip().lower()
    if tipo not in ('entrada', 'salida'):
        flash('Tipo de movimiento no válido.', 'danger')
        return redirect(url_for('caja.index'))

    concepto = request.form.get('concepto', '').strip()
    if not concepto:
        flash('Debes indicar un concepto o motivo para el movimiento.', 'danger')
        return redirect(url_for('caja.index'))

    try:
        monto_raw = request.form.get('monto', '0').replace(',', '.').strip()
        monto = float(monto_raw)
    except ValueError:
        flash('El importe introducido no es válido.', 'danger')
        return redirect(url_for('caja.index'))

    if monto <= 0:
        flash('El importe debe ser mayor que 0 €.', 'danger')
        return redirect(url_for('caja.index'))

    # Aviso si la salida supera el efectivo esperado
    if tipo == 'salida':
        resumen = caja_activa.calcular_resumen()
        if monto > resumen['efectivo_esperado']:
            flash('Atención: La salida supera el efectivo teórico estimado en caja.', 'warning')

    mov = MovimientoCaja(
        caja_sesion_id=caja_activa.id,
        tipo=tipo,
        concepto=concepto,
        monto=monto,
        usuario_id=current_user.id
    )
    db.session.add(mov)
    db.session.commit()

    tipo_label = 'Entrada' if tipo == 'entrada' else 'Salida'
    flash(f'{tipo_label} de {monto:,.2f} € registrada correctamente.', 'success')
    return redirect(url_for('caja.index'))


@caja.route('/cerrar', methods=['GET', 'POST'])
@login_required
def cerrar():
    """Arqueo y cierre de la caja activa."""
    caja_activa = query_negocio(CajaSesion).filter_by(estado='abierta')\
        .order_by(CajaSesion.fecha_apertura.desc()).first()

    if not caja_activa:
        flash('No hay ninguna caja abierta para cerrar.', 'warning')
        return redirect(url_for('caja.index'))

    resumen = caja_activa.calcular_resumen()

    if request.method == 'POST':
        try:
            monto_raw = request.form.get('monto_real', '0').replace(',', '.').strip()
            monto_real = float(monto_raw)
        except ValueError:
            flash('El importe físico contado no es válido.', 'danger')
            return redirect(url_for('caja.cerrar'))

        if monto_real < 0:
            flash('El efectivo contado no puede ser negativo.', 'danger')
            return redirect(url_for('caja.cerrar'))

        notas_cierre = request.form.get('notas_cierre', '').strip()
        monto_esperado = resumen['efectivo_esperado']
        diferencia = round(monto_real - monto_esperado, 2)

        caja_activa.fecha_cierre = datetime.utcnow()
        caja_activa.usuario_cierre_id = current_user.id
        caja_activa.monto_esperado = monto_esperado
        caja_activa.monto_real = monto_real
        caja_activa.diferencia = diferencia
        caja_activa.notas_cierre = notas_cierre or None
        caja_activa.estado = 'cerrada'

        db.session.commit()

        if abs(diferencia) < 0.01:
            flash('¡Caja cerrada y cuadrada a la perfección (0.00 € de descuadre)!', 'success')
        elif diferencia > 0:
            flash(f'Caja cerrada con un SOBRANTE de +{diferencia:,.2f} €.', 'info')
        else:
            flash(f'Caja cerrada con un FALTANTE de {diferencia:,.2f} €.', 'danger')

        return redirect(url_for('caja.detalle', id=caja_activa.id))

    return render_template('caja/cerrar.html', caja=caja_activa, resumen=resumen)


@caja.route('/historial')
@login_required
def historial():
    """Listado paginado de sesiones de caja."""
    page = request.args.get('page', 1, type=int)
    cajas = query_negocio(CajaSesion)\
        .order_by(CajaSesion.fecha_apertura.desc())\
        .paginate(page=page, per_page=15, error_out=False)

    return render_template('caja/historial.html', cajas=cajas)


@caja.route('/detalle/<int:id>')
@login_required
def detalle(id):
    """Detalle completo de una sesión de caja pasada o activa."""
    caja_obj = get_negocio_o_404(CajaSesion, id)
    resumen = caja_obj.calcular_resumen()

    fecha_fin = caja_obj.fecha_cierre or datetime.utcnow()

    # Movimientos manuales
    movimientos = caja_obj.movimientos.order_by(MovimientoCaja.fecha.asc()).all()

    # Transferencias asociadas al turno
    transacciones = query_negocio(Transaccion)\
        .filter(Transaccion.fecha >= caja_obj.fecha_apertura, Transaccion.fecha <= fecha_fin)\
        .order_by(Transaccion.fecha.asc()).all()

    # Ventas de productos asociadas al turno
    ventas = query_negocio(MovimientoProducto)\
        .filter(
            MovimientoProducto.tipo == 'venta',
            MovimientoProducto.fecha >= caja_obj.fecha_apertura,
            MovimientoProducto.fecha <= fecha_fin
        ).order_by(MovimientoProducto.fecha.asc()).all()

    return render_template(
        'caja/detalle.html',
        caja=caja_obj,
        resumen=resumen,
        movimientos=movimientos,
        transacciones=transacciones,
        ventas=ventas
    )


@caja.route('/imprimir/<int:id>')
@login_required
def imprimir(id):
    """Recibo térmico imprimible (80mm) de cierre de caja."""
    caja_obj = get_negocio_o_404(CajaSesion, id)
    resumen = caja_obj.calcular_resumen()
    movimientos = caja_obj.movimientos.order_by(MovimientoCaja.fecha.asc()).all()

    return render_template(
        'caja/ticket.html',
        caja=caja_obj,
        resumen=resumen,
        movimientos=movimientos
    )
