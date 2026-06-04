"""
Utilidades para importación de datos desde archivos CSV
"""
import csv
import io
from datetime import datetime
from werkzeug.utils import secure_filename


def validar_archivo_csv(file):
    """Valida que el archivo sea un CSV válido."""
    if not file:
        return False, "No se proporcionó ningún archivo"
    
    if not file.filename:
        return False, "El archivo no tiene nombre"
    
    if not file.filename.lower().endswith('.csv'):
        return False, "El archivo debe ser formato CSV"
    
    return True, "Archivo válido"


def procesar_csv_clientes(file_content):
    """
    Procesa el contenido de un CSV de clientes y retorna los datos validados.
    
    Formato esperado del CSV:
    Nombre,Apellido,Documento,Teléfono,Fecha Nacimiento (YYYY-MM-DD)
    """
    resultados = {
        'exito': [],
        'errores': [],
        'duplicados': []
    }
    
    # Decodificar contenido
    try:
        content = file_content.decode('utf-8-sig')  # utf-8-sig para manejar BOM
    except:
        try:
            content = file_content.decode('latin-1')
        except:
            resultados['errores'].append({
                'linea': 0,
                'error': 'No se pudo decodificar el archivo. Use codificación UTF-8.'
            })
            return resultados
    
    # Leer CSV
    csv_file = io.StringIO(content)
    reader = csv.DictReader(csv_file)
    
    # Validar encabezados
    required_fields = ['Nombre', 'Apellido', 'Documento']
    if not all(field in reader.fieldnames for field in required_fields):
        resultados['errores'].append({
            'linea': 0,
            'error': f'Faltan columnas requeridas. Se esperan: {", ".join(required_fields)}'
        })
        return resultados
    
    # Procesar cada línea
    for idx, row in enumerate(reader, start=2):  # Start at 2 because line 1 is header
        try:
            # Validar campos obligatorios
            if not row.get('Nombre') or not row.get('Apellido') or not row.get('Documento'):
                resultados['errores'].append({
                    'linea': idx,
                    'error': 'Faltan campos obligatorios (Nombre, Apellido, Documento)',
                    'datos': row
                })
                continue
            
            # Validar y convertir fecha de nacimiento
            fecha_nacimiento = None
            if row.get('Fecha Nacimiento'):
                try:
                    fecha_nacimiento = datetime.strptime(row['Fecha Nacimiento'].strip(), '%Y-%m-%d').date()
                except ValueError:
                    resultados['errores'].append({
                        'linea': idx,
                        'error': 'Formato de fecha incorrecto. Use YYYY-MM-DD',
                        'datos': row
                    })
                    continue
            
            # Preparar datos del cliente
            cliente_data = {
                'nombre': row['Nombre'].strip(),
                'apellido': row['Apellido'].strip(),
                'documento': row['Documento'].strip(),
                'telefono': row.get('Teléfono', '').strip() or row.get('Telefono', '').strip(),
                'fecha_nacimiento': fecha_nacimiento
            }
            
            # Verificar duplicados en la base de datos
            from app.models.cliente import Cliente
            existente = Cliente.query.filter_by(documento=cliente_data['documento']).first()
            
            if existente:
                resultados['duplicados'].append({
                    'linea': idx,
                    'documento': cliente_data['documento'],
                    'nombre': f"{cliente_data['nombre']} {cliente_data['apellido']}",
                    'cliente_existente_id': existente.id
                })
            else:
                resultados['exito'].append({
                    'linea': idx,
                    'datos': cliente_data
                })
                
        except Exception as e:
            resultados['errores'].append({
                'linea': idx,
                'error': f'Error al procesar: {str(e)}',
                'datos': row
            })
    
    return resultados


def importar_clientes_validados(clientes_data):
    """
    Importa los clientes validados a la base de datos.
    
    Args:
        clientes_data: Lista de diccionarios con datos de clientes validados
    
    Returns:
        Tupla (cantidad_importados, errores)
    """
    from app.models.cliente import Cliente
    from app.extensions import db
    
    importados = 0
    errores = []
    
    for item in clientes_data:
        try:
            datos = item['datos']
            
            nuevo_cliente = Cliente(
                nombre=datos['nombre'],
                apellido=datos['apellido'],
                documento=datos['documento'],
                telefono=datos['telefono'],
                fecha_nacimiento=datos['fecha_nacimiento'],
                fecha_registro=datetime.now(),
                ultima_visita=datetime.now()
            )
            
            db.session.add(nuevo_cliente)
            importados += 1
            
        except Exception as e:
            errores.append({
                'linea': item['linea'],
                'error': f'Error al guardar: {str(e)}'
            })
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return 0, [{'error': f'Error al guardar en base de datos: {str(e)}'}]
    
    return importados, errores


def generar_plantilla_csv_clientes():
    """Genera una plantilla CSV de ejemplo para importar clientes."""
    from flask import make_response
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Encabezados
    writer.writerow(['Nombre', 'Apellido', 'Documento', 'Teléfono', 'Fecha Nacimiento'])
    
    # Ejemplos
    writer.writerow(['Juan', 'Pérez', 'X1234567A', '612345678', '1985-05-15'])
    writer.writerow(['María', 'García', 'Y9876543B', '623456789', '1990-08-20'])
    writer.writerow(['Pedro', 'López', 'Z5555555C', '634567890', '1978-12-01'])
    
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=plantilla_clientes.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    
    return response
