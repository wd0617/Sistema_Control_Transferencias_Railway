from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required
from app.decorators import admin_required
from app.models.cliente import Cliente
from app.models.transaccion import Transaccion
from app.utils.export_utils import (
    generar_csv_clientes, generar_csv_transacciones,
    generar_excel_clientes, generar_excel_transacciones,
    generar_reporte_pdf_cliente
)
from app.utils.import_utils import (
    validar_archivo_csv, procesar_csv_clientes,
    importar_clientes_validados, generar_plantilla_csv_clientes
)
from datetime import datetime

data_mgmt = Blueprint('data_mgmt', __name__)


@data_mgmt.route('/')
@login_required
@admin_required
def index():
    """Panel principal de gestión de datos."""
    # Estadísticas
    total_clientes = Cliente.query.count()
    total_transacciones = Transaccion.query.count()
    
    return render_template('data_management/index.html',
                          total_clientes=total_clientes,
                          total_transacciones=total_transacciones,
                          now=datetime.now())


# ==================== EXPORTACIÓN ====================

@data_mgmt.route('/exportar/clientes/csv')
@login_required
@admin_required
def exportar_clientes_csv():
    """Exporta todos los clientes a CSV."""
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    return generar_csv_clientes(clientes)


@data_mgmt.route('/exportar/clientes/excel')
@login_required
@admin_required
def exportar_clientes_excel():
    """Exporta todos los clientes a Excel."""
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    return generar_excel_clientes(clientes)


@data_mgmt.route('/exportar/transacciones/csv')
@login_required
@admin_required
def exportar_transacciones_csv():
    """Exporta todas las transacciones a CSV."""
    transacciones = Transaccion.query.order_by(Transaccion.fecha.desc()).all()
    return generar_csv_transacciones(transacciones)


@data_mgmt.route('/exportar/transacciones/excel')
@login_required
@admin_required
def exportar_transacciones_excel():
    """Exporta todas las transacciones a Excel."""
    transacciones = Transaccion.query.order_by(Transaccion.fecha.desc()).all()
    return generar_excel_transacciones(transacciones)


@data_mgmt.route('/exportar/cliente/<int:cliente_id>/pdf')
@login_required
@admin_required
def exportar_cliente_pdf(cliente_id):
    """Genera un reporte PDF para un cliente específico."""
    cliente = Cliente.query.get_or_404(cliente_id)
    transacciones = Transaccion.query.filter_by(cliente_id=cliente_id).order_by(Transaccion.fecha.desc()).all()
    
    pdf = generar_reporte_pdf_cliente(cliente, transacciones)
    
    if pdf:
        return pdf
    else:
        flash('La generación de PDF no está disponible. Instale reportlab.', 'warning')
        return redirect(url_for('transacciones.cliente_historial', cliente_id=cliente_id))


# ==================== IMPORTACIÓN ====================

@data_mgmt.route('/importar', methods=['GET', 'POST'])
@login_required
@admin_required
def importar():
    """Página de importación de clientes."""
    if request.method == 'POST':
        # Verificar que se subió un archivo
        if 'archivo' not in request.files:
            flash('No se seleccionó ningún archivo', 'danger')
            return redirect(url_for('data_mgmt.importar'))
        
        file = request.files['archivo']
        
        # Validar archivo
        valido, mensaje = validar_archivo_csv(file)
        if not valido:
            flash(mensaje, 'danger')
            return redirect(url_for('data_mgmt.importar'))
        
        # Leer y procesar archivo
        file_content = file.read()
        resultados = procesar_csv_clientes(file_content)
        
        # Guardar resultados en sesión para la vista de confirmación
        session['import_resultados'] = {
            'exito': resultados['exito'],
            'errores': resultados['errores'],
            'duplicados': resultados['duplicados'],
            'total_lineas': len(resultados['exito']) + len(resultados['errores']) + len(resultados['duplicados'])
        }
        
        return redirect(url_for('data_mgmt.confirmar_importacion'))
    
    # GET: Mostrar formulario
    return render_template('data_management/importar.html', now=datetime.now())


@data_mgmt.route('/importar/confirmar', methods=['GET', 'POST'])
@login_required
@admin_required
def confirmar_importacion():
    """Confirma y ejecuta la importación de clientes."""
    # Obtener resultados de la sesión
    resultados = session.get('import_resultados')
    
    if not resultados:
        flash('No hay datos de importación pendientes', 'warning')
        return redirect(url_for('data_mgmt.importar'))
    
    if request.method == 'POST':
        # Usuario confirmó la importación
        if resultados['exito']:
            importados, errores_import = importar_clientes_validados(resultados['exito'])
            
            if importados > 0:
                flash(f'Se importaron {importados} clientes correctamente', 'success')
            
            if errores_import:
                for error in errores_import:
                    flash(f"Error en línea {error.get('linea', 'N/A')}: {error['error']}", 'danger')
        else:
            flash('No hay clientes válidos para importar', 'warning')
        
        # Limpiar sesión
        session.pop('import_resultados', None)
        
        return redirect(url_for('clientes.lista'))
    
    # GET: Mostrar vista de confirmación
    return render_template('data_management/confirmar_importacion.html',
                          resultados=resultados,
                          now=datetime.now())


@data_mgmt.route('/importar/cancelar')
@login_required
@admin_required
def cancelar_importacion():
    """Cancela la importación pendiente."""
    session.pop('import_resultados', None)
    flash('Importación cancelada', 'info')
    return redirect(url_for('data_mgmt.importar'))


@data_mgmt.route('/plantilla/clientes')
@login_required
@admin_required
def descargar_plantilla_clientes():
    """Descarga una plantilla CSV de ejemplo para importar clientes."""
    return generar_plantilla_csv_clientes()
