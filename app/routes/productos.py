from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.producto import Producto, MovimientoProducto
from datetime import datetime, timedelta

productos = Blueprint('productos', __name__)


@productos.route('/')
@login_required
def lista():
    """Lista de productos activos con stock."""
    productos_list = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()
    return render_template('productos/lista.html', productos=productos_list, now=datetime.now())


@productos.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    """Crear un nuevo producto."""
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        tipo_medida = request.form.get('tipo_medida', 'unidad')
        precio_str = request.form.get('precio', '').strip()

        if not nombre or not precio_str:
            flash('Nombre y precio son obligatorios', 'danger')
            return redirect(url_for('productos.nuevo'))

        try:
            precio = float(precio_str.replace(',', '.'))
        except ValueError:
            flash('El precio no es válido', 'danger')
            return redirect(url_for('productos.nuevo'))

        producto = Producto(
            nombre=nombre,
            tipo_medida=tipo_medida,
            precio=precio
        )
        db.session.add(producto)
        db.session.commit()
        flash(f'Producto "{nombre}" creado correctamente', 'success')
        return redirect(url_for('productos.lista'))

    return render_template('productos/nuevo.html')


@productos.route('/editar/<int:producto_id>', methods=['GET', 'POST'])
@login_required
def editar(producto_id):
    """Editar nombre y precio de un producto."""
    producto = Producto.query.get_or_404(producto_id)

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        precio_str = request.form.get('precio', '').strip()

        if not nombre or not precio_str:
            flash('Nombre y precio son obligatorios', 'danger')
            return redirect(url_for('productos.editar', producto_id=producto.id))

        try:
            precio = float(precio_str.replace(',', '.'))
        except ValueError:
            flash('El precio no es válido', 'danger')
            return redirect(url_for('productos.editar', producto_id=producto.id))

        producto.nombre = nombre
        producto.precio = precio
        db.session.commit()
        flash(f'Producto actualizado correctamente', 'success')
        return redirect(url_for('productos.lista'))

    return render_template('productos/editar.html', producto=producto)


@productos.route('/entrada', methods=['GET', 'POST'])
@login_required
def entrada():
    """Registrar entrada de stock."""
    if request.method == 'POST':
        producto_id = request.form.get('producto_id', type=int)
        cantidad_str = request.form.get('cantidad', '').strip()
        notas = request.form.get('notas', '').strip()

        if not producto_id or not cantidad_str:
            flash('Producto y cantidad son obligatorios', 'danger')
            return redirect(url_for('productos.entrada'))

        try:
            cantidad = float(cantidad_str.replace(',', '.'))
        except ValueError:
            flash('La cantidad no es válida', 'danger')
            return redirect(url_for('productos.entrada'))

        if cantidad <= 0:
            flash('La cantidad debe ser mayor a cero', 'danger')
            return redirect(url_for('productos.entrada'))

        producto = Producto.query.get_or_404(producto_id)
        producto.stock_actual += cantidad

        movimiento = MovimientoProducto(
            producto_id=producto.id,
            tipo='entrada',
            cantidad=cantidad,
            notas=notas or None,
            usuario_id=current_user.id
        )
        db.session.add(movimiento)
        db.session.commit()

        flash(f'Entrada registrada: +{cantidad} {producto.label_medida()} de {producto.nombre}', 'success')
        return redirect(url_for('productos.lista'))

    productos_list = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()
    return render_template('productos/entrada.html', productos=productos_list)


@productos.route('/venta', methods=['GET', 'POST'])
@login_required
def venta():
    """Registrar venta de producto."""
    if request.method == 'POST':
        producto_id = request.form.get('producto_id', type=int)
        cantidad_str = request.form.get('cantidad', '').strip()
        notas = request.form.get('notas', '').strip()

        if not producto_id or not cantidad_str:
            flash('Producto y cantidad son obligatorios', 'danger')
            return redirect(url_for('productos.venta'))

        try:
            cantidad = float(cantidad_str.replace(',', '.'))
        except ValueError:
            flash('La cantidad no es válida', 'danger')
            return redirect(url_for('productos.venta'))

        if cantidad <= 0:
            flash('La cantidad debe ser mayor a cero', 'danger')
            return redirect(url_for('productos.venta'))

        producto = Producto.query.get_or_404(producto_id)

        if producto.stock_actual < cantidad:
            flash(f'Stock insuficiente. Disponible: {producto.stock_actual} {producto.label_medida()}', 'danger')
            return redirect(url_for('productos.venta'))

        producto.stock_actual -= cantidad
        total = round(cantidad * producto.precio, 2)

        movimiento = MovimientoProducto(
            producto_id=producto.id,
            tipo='venta',
            cantidad=cantidad,
            precio_unitario_momento=producto.precio,
            total=total,
            notas=notas or None,
            usuario_id=current_user.id
        )
        db.session.add(movimiento)
        db.session.commit()

        flash(f'Venta registrada: {cantidad} {producto.label_medida()} de {producto.nombre} = {total:.2f}€', 'success')
        return redirect(url_for('productos.lista'))

    productos_list = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()
    return render_template('productos/venta.html', productos=productos_list)


@productos.route('/movimientos')
@login_required
def movimientos():
    """Historial de movimientos con filtros opcionales."""
    tipo = request.args.get('tipo', '')
    desde_str = request.args.get('desde', '')
    hasta_str = request.args.get('hasta', '')

    query = MovimientoProducto.query.join(Producto).order_by(MovimientoProducto.fecha.desc())

    if tipo in ('entrada', 'venta'):
        query = query.filter(MovimientoProducto.tipo == tipo)

    if desde_str:
        try:
            desde = datetime.strptime(desde_str, '%Y-%m-%d')
            query = query.filter(MovimientoProducto.fecha >= desde)
        except ValueError:
            pass

    if hasta_str:
        try:
            hasta = datetime.strptime(hasta_str, '%Y-%m-%d')
            query = query.filter(MovimientoProducto.fecha < hasta + timedelta(days=1))
        except ValueError:
            pass

    movimientos_list = query.all()

    # Totales
    total_ventas = db.session.query(db.func.sum(MovimientoProducto.total)).filter(
        MovimientoProducto.tipo == 'venta'
    ).scalar() or 0

    return render_template('productos/movimientos.html',
                           movimientos=movimientos_list,
                           total_ventas=float(total_ventas),
                           tipo=tipo,
                           desde=desde_str,
                           hasta=hasta_str,
                           now=datetime.now())


@productos.route('/eliminar/<int:producto_id>', methods=['POST'])
@login_required
def eliminar(producto_id):
    """Desactivar (eliminar lógicamente) un producto."""
    producto = Producto.query.get_or_404(producto_id)
    producto.activo = False
    db.session.commit()
    flash(f'Producto "{producto.nombre}" eliminado', 'success')
    return redirect(url_for('productos.lista'))
