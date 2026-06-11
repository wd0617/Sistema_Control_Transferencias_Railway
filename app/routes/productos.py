import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.producto import Producto, MovimientoProducto
from datetime import datetime, timedelta

productos = Blueprint('productos', __name__)

ALLOWED_IMG = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMG


def _guardar_foto(archivo):
    if not archivo or archivo.filename == '':
        return None
    if not _allowed_file(archivo.filename):
        return None
    filename = secure_filename(archivo.filename)
    # Evitar colisiones con timestamp
    name, ext = os.path.splitext(filename)
    filename = f"{name}_{int(datetime.utcnow().timestamp())}{ext}"
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'productos')
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    archivo.save(filepath)
    return f"productos/{filename}"


def _eliminar_foto(ruta_relativa):
    if not ruta_relativa:
        return
    try:
        full = os.path.join(current_app.config['UPLOAD_FOLDER'], ruta_relativa)
        if os.path.exists(full):
            os.remove(full)
    except Exception:
        pass


@productos.route('/')
@login_required
def lista():
    """Lista de productos activos con filtros y vista."""
    categoria = request.args.get('categoria', '')
    vista = request.args.get('vista', 'lista')

    query = Producto.query.filter_by(activo=True)
    if categoria:
        query = query.filter_by(categoria=categoria)
    productos_list = query.order_by(Producto.nombre).all()

    return render_template('productos/lista.html',
                           productos=productos_list,
                           categoria_activa=categoria,
                           vista=vista,
                           categorias=Producto.CATEGORIAS,
                           now=datetime.now())


@productos.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    """Crear un nuevo producto."""
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        categoria = request.form.get('categoria', 'procesados')
        tipo_medida = request.form.get('tipo_medida', 'unidad')
        precio_str = request.form.get('precio', '').strip()
        foto_file = request.files.get('foto')

        if not nombre or not precio_str:
            flash('Nombre y precio son obligatorios', 'danger')
            return redirect(url_for('productos.nuevo'))

        try:
            precio = float(precio_str.replace(',', '.'))
        except ValueError:
            flash('El precio no es válido', 'danger')
            return redirect(url_for('productos.nuevo'))

        foto_ruta = _guardar_foto(foto_file)

        producto = Producto(
            nombre=nombre,
            categoria=categoria,
            tipo_medida=tipo_medida,
            precio=precio,
            foto=foto_ruta
        )
        db.session.add(producto)
        db.session.commit()
        flash(f'Producto "{nombre}" creado correctamente', 'success')
        return redirect(url_for('productos.lista'))

    return render_template('productos/nuevo.html', categorias=Producto.CATEGORIAS)


@productos.route('/editar/<int:producto_id>', methods=['GET', 'POST'])
@login_required
def editar(producto_id):
    """Editar nombre, precio, categoria y foto de un producto."""
    producto = Producto.query.get_or_404(producto_id)

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        categoria = request.form.get('categoria', producto.categoria)
        precio_str = request.form.get('precio', '').strip()
        foto_file = request.files.get('foto')
        eliminar_foto = request.form.get('eliminar_foto')

        if not nombre or not precio_str:
            flash('Nombre y precio son obligatorios', 'danger')
            return redirect(url_for('productos.editar', producto_id=producto.id))

        try:
            precio = float(precio_str.replace(',', '.'))
        except ValueError:
            flash('El precio no es válido', 'danger')
            return redirect(url_for('productos.editar', producto_id=producto.id))

        if eliminar_foto and producto.foto:
            _eliminar_foto(producto.foto)
            producto.foto = None
        elif foto_file and foto_file.filename:
            nueva_ruta = _guardar_foto(foto_file)
            if nueva_ruta:
                if producto.foto:
                    _eliminar_foto(producto.foto)
                producto.foto = nueva_ruta

        producto.nombre = nombre
        producto.categoria = categoria
        producto.precio = precio
        db.session.commit()
        flash('Producto actualizado correctamente', 'success')
        return redirect(url_for('productos.lista'))

    return render_template('productos/editar.html', producto=producto, categorias=Producto.CATEGORIAS)


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
    if producto.foto:
        _eliminar_foto(producto.foto)
    producto.activo = False
    db.session.commit()
    flash(f'Producto "{producto.nombre}" eliminado', 'success')
    return redirect(url_for('productos.lista'))
