import os
import re
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func
from app import db
from app.models.producto import Producto, MovimientoProducto
from datetime import datetime, timedelta

productos = Blueprint('productos', __name__)


@productos.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    """Sirve archivos subidos (fotos de productos)."""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

ALLOWED_IMG = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def _cloudinary_configured():
    return bool(os.environ.get('CLOUDINARY_CLOUD_NAME'))


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMG


def _guardar_foto(archivo):
    if not archivo or archivo.filename == '':
        return None
    if not _allowed_file(archivo.filename):
        return None

    # Si Cloudinary está configurado, subir allá
    if _cloudinary_configured():
        try:
            import cloudinary.uploader
            filename = secure_filename(archivo.filename)
            name, ext = os.path.splitext(filename)
            public_id = f"productos/{name}_{int(datetime.utcnow().timestamp())}"
            result = cloudinary.uploader.upload(archivo, public_id=public_id, overwrite=True)
            return result.get('secure_url')
        except Exception as e:
            current_app.logger.warning(f'Error subiendo a Cloudinary: {e}')
            # Fallback a local si falla Cloudinary

    # Guardado local (fallback)
    filename = secure_filename(archivo.filename)
    name, ext = os.path.splitext(filename)
    filename = f"{name}_{int(datetime.utcnow().timestamp())}{ext}"
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'productos')
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    archivo.save(filepath)
    return f"productos/{filename}"


def _extraer_cloudinary_public_id(url):
    """Extrae el public_id de una URL de Cloudinary."""
    if not url or 'res.cloudinary.com' not in url:
        return None
    m = re.search(r'/image/upload/(?:v\d+/)?(.+?)\.[^.]+$', url)
    if m:
        return m.group(1)
    return None


def _eliminar_foto(ruta_o_url):
    if not ruta_o_url:
        return

    # Si es una URL de Cloudinary, eliminar de allá
    public_id = _extraer_cloudinary_public_id(ruta_o_url)
    if public_id and _cloudinary_configured():
        try:
            import cloudinary.uploader
            cloudinary.uploader.destroy(public_id)
            return
        except Exception as e:
            current_app.logger.warning(f'Error eliminando de Cloudinary: {e}')

    # Fallback: eliminar archivo local
    try:
        full = os.path.join(current_app.config['UPLOAD_FOLDER'], ruta_o_url)
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

        unidades = request.form.get('unidades', '').strip()
        unidades_int = int(unidades) if unidades.isdigit() else None

        movimiento = MovimientoProducto(
            producto_id=producto.id,
            tipo='entrada',
            cantidad=cantidad,
            unidades=unidades_int,
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

        unidades = request.form.get('unidades', '').strip()
        unidades_int = int(unidades) if unidades.isdigit() else None

        movimiento = MovimientoProducto(
            producto_id=producto.id,
            tipo='venta',
            cantidad=cantidad,
            precio_unitario_momento=producto.precio,
            total=total,
            unidades=unidades_int,
            notas=notas or None,
            usuario_id=current_user.id
        )
        db.session.add(movimiento)
        db.session.commit()

        flash(f'Venta registrada: {cantidad} {producto.label_medida()} de {producto.nombre} = {total:.2f}€', 'success')
        return redirect(url_for('productos.lista'))

    productos_list = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()
    return render_template('productos/venta.html', productos=productos_list)


@productos.route('/dashboard')
@login_required
def dashboard():
    """Panel visual de ventas de productos y estado de stock."""
    ahora = datetime.now()
    hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = hoy_inicio + timedelta(days=1)

    # Ventas de hoy
    ventas_hoy = MovimientoProducto.query.filter(
        MovimientoProducto.tipo == 'venta',
        MovimientoProducto.fecha >= hoy_inicio,
        MovimientoProducto.fecha < hoy_fin
    ).order_by(MovimientoProducto.fecha.asc()).all()

    total_vendido_hoy = sum(v.total or 0 for v in ventas_hoy)
    cantidad_ventas_hoy = len(ventas_hoy)

    # Ventas por producto hoy (para gráfico)
    ventas_por_producto = db.session.query(
        Producto.nombre,
        func.sum(MovimientoProducto.total).label('total'),
        func.sum(MovimientoProducto.cantidad).label('cantidad')
    ).join(MovimientoProducto).filter(
        MovimientoProducto.tipo == 'venta',
        MovimientoProducto.fecha >= hoy_inicio,
        MovimientoProducto.fecha < hoy_fin
    ).group_by(Producto.nombre).order_by(func.sum(MovimientoProducto.total).desc()).all()

    # Ventas por hora hoy (para gráfico de líneas)
    ventas_por_hora_raw = db.session.query(
        func.extract('hour', MovimientoProducto.fecha).label('hora'),
        func.sum(MovimientoProducto.total).label('total')
    ).filter(
        MovimientoProducto.tipo == 'venta',
        MovimientoProducto.fecha >= hoy_inicio,
        MovimientoProducto.fecha < hoy_fin
    ).group_by(func.extract('hour', MovimientoProducto.fecha)).order_by('hora').all()

    horas = list(range(24))
    totales_por_hora = [0.0] * 24
    for hora, total in ventas_por_hora_raw:
        if hora is not None and 0 <= int(hora) < 24:
            totales_por_hora[int(hora)] = float(total or 0)

    # Estado de stock
    productos_agotados = Producto.query.filter_by(activo=True).filter(Producto.stock_actual <= 0).order_by(Producto.nombre).all()
    productos_bajo_stock = Producto.query.filter_by(activo=True).filter(Producto.stock_actual > 0, Producto.stock_actual < 5).order_by(Producto.nombre).all()

    # Últimas ventas (top 10)
    ultimas_ventas = MovimientoProducto.query.filter(
        MovimientoProducto.tipo == 'venta'
    ).order_by(MovimientoProducto.fecha.desc()).limit(10).all()

    return render_template('productos/dashboard.html',
                           ahora=ahora,
                           total_vendido_hoy=total_vendido_hoy,
                           cantidad_ventas_hoy=cantidad_ventas_hoy,
                           ventas_por_producto=ventas_por_producto,
                           horas=horas,
                           totales_por_hora=totales_por_hora,
                           productos_agotados=productos_agotados,
                           productos_bajo_stock=productos_bajo_stock,
                           ultimas_ventas=ultimas_ventas,
                           now=ahora)


@productos.route('/agotar/<int:producto_id>', methods=['POST'])
@login_required
def agotar(producto_id):
    """Marca un producto como agotado: stock a cero y registra ajuste."""
    producto = Producto.query.get_or_404(producto_id)

    if producto.stock_actual <= 0:
        flash(f'{producto.nombre} ya está agotado.', 'info')
        return redirect(url_for('productos.lista'))

    cantidad_ajuste = producto.stock_actual
    producto.stock_actual = 0

    movimiento = MovimientoProducto(
        producto_id=producto.id,
        tipo='ajuste',
        cantidad=cantidad_ajuste,
        precio_unitario_momento=0,
        total=0,
        notas='Marcado como agotado: stock sin contar / terminado',
        usuario_id=current_user.id
    )
    db.session.add(movimiento)
    db.session.commit()

    flash(f'{producto.nombre} marcado como agotado (ajuste de {cantidad_ajuste:.2f} {producto.label_medida()}).', 'warning')
    return redirect(url_for('productos.lista'))


@productos.route('/movimientos')
@login_required
def movimientos():
    """Historial de movimientos con filtros opcionales."""
    tipo = request.args.get('tipo', '')
    desde_str = request.args.get('desde', '')
    hasta_str = request.args.get('hasta', '')

    query = MovimientoProducto.query.join(Producto).order_by(MovimientoProducto.fecha.desc())

    # Ajuste se muestra siempre, salvo que filtren explícitamente por tipo
    if tipo in ('entrada', 'venta', 'ajuste'):
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

    # Totales filtrados
    total_ventas = db.session.query(func.sum(MovimientoProducto.total)).filter(
        MovimientoProducto.tipo == 'venta'
    )
    if desde_str:
        total_ventas = total_ventas.filter(MovimientoProducto.fecha >= datetime.strptime(desde_str, '%Y-%m-%d'))
    if hasta_str:
        total_ventas = total_ventas.filter(MovimientoProducto.fecha < datetime.strptime(hasta_str, '%Y-%m-%d') + timedelta(days=1))
    total_ventas = total_ventas.scalar() or 0

    # Total vendido hoy (siempre visible)
    hoy_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = hoy_inicio + timedelta(days=1)
    total_hoy = db.session.query(func.sum(MovimientoProducto.total)).filter(
        MovimientoProducto.tipo == 'venta',
        MovimientoProducto.fecha >= hoy_inicio,
        MovimientoProducto.fecha < hoy_fin
    ).scalar() or 0

    return render_template('productos/movimientos.html',
                           movimientos=movimientos_list,
                           total_ventas=float(total_ventas),
                           total_hoy=float(total_hoy),
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
