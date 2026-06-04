"""
Utilidades para exportación de datos a CSV, Excel y PDF
"""
import csv
import io
from datetime import datetime
from flask import make_response


def generar_csv_clientes(clientes):
    """Genera un archivo CSV con la información de clientes."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Encabezados
    writer.writerow([
        'ID', 'Nombre', 'Apellido', 'Documento', 'Teléfono', 
        'Fecha Nacimiento', 'Fecha Registro', 'Última Visita'
    ])
    
    # Datos
    for cliente in clientes:
        writer.writerow([
            cliente.id,
            cliente.nombre,
            cliente.apellido,
            cliente.documento,
            cliente.telefono or '',
            cliente.fecha_nacimiento.strftime('%Y-%m-%d') if cliente.fecha_nacimiento else '',
            cliente.fecha_registro.strftime('%Y-%m-%d %H:%M') if cliente.fecha_registro else '',
            cliente.ultima_visita.strftime('%Y-%m-%d %H:%M') if cliente.ultima_visita else ''
        ])
    
    # Crear respuesta
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=clientes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    
    return response


def generar_csv_transacciones(transacciones):
    """Genera un archivo CSV con la información de transacciones."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Encabezados
    writer.writerow([
        'ID', 'Fecha', 'Cliente', 'Documento Cliente', 'Servicio', 
        'Monto', 'Comisión', 'Referencia', 'Notas'
    ])
    
    # Datos
    for trans in transacciones:
        writer.writerow([
            trans.id,
            trans.fecha.strftime('%Y-%m-%d %H:%M') if trans.fecha else '',
            trans.cliente.nombre_completo() if trans.cliente else '',
            trans.cliente.documento if trans.cliente else '',
            trans.servicio.nombre if trans.servicio else '',
            trans.monto,
            trans.comision,
            trans.referencia or '',
            trans.notas or ''
        ])
    
    # Crear respuesta
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=transacciones_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    
    return response


def generar_excel_clientes(clientes):
    """Genera un archivo Excel con la información de clientes."""
    try:
        import pandas as pd
        from io import BytesIO
        
        # Crear DataFrame
        datos = []
        for cliente in clientes:
            datos.append({
                'ID': cliente.id,
                'Nombre': cliente.nombre,
                'Apellido': cliente.apellido,
                'Documento': cliente.documento,
                'Teléfono': cliente.telefono or '',
                'Fecha Nacimiento': cliente.fecha_nacimiento.strftime('%Y-%m-%d') if cliente.fecha_nacimiento else '',
                'Fecha Registro': cliente.fecha_registro.strftime('%Y-%m-%d %H:%M') if cliente.fecha_registro else '',
                'Última Visita': cliente.ultima_visita.strftime('%Y-%m-%d %H:%M') if cliente.ultima_visita else '',
                'Saldo Disponible': cliente.calcular_saldo_disponible()
            })
        
        df = pd.DataFrame(datos)
        
        # Crear archivo Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Clientes')
        
        output.seek(0)
        
        # Crear respuesta
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=clientes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        return response
        
    except ImportError:
        # Si pandas no está disponible, usar CSV como alternativa
        return generar_csv_clientes(clientes)


def generar_excel_transacciones(transacciones):
    """Genera un archivo Excel con la información de transacciones."""
    try:
        import pandas as pd
        from io import BytesIO
        
        # Crear DataFrame
        datos = []
        for trans in transacciones:
            datos.append({
                'ID': trans.id,
                'Fecha': trans.fecha.strftime('%Y-%m-%d %H:%M') if trans.fecha else '',
                'Cliente': trans.cliente.nombre_completo() if trans.cliente else '',
                'Documento Cliente': trans.cliente.documento if trans.cliente else '',
                'Servicio': trans.servicio.nombre if trans.servicio else '',
                'Monto (€)': trans.monto,
                'Comisión (€)': trans.comision,
                'Total (€)': trans.monto + trans.comision,
                'Referencia': trans.referencia or '',
                'Notas': trans.notas or ''
            })
        
        df = pd.DataFrame(datos)
        
        # Crear archivo Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Transacciones')
        
        output.seek(0)
        
        # Crear respuesta
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=transacciones_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        return response
        
    except ImportError:
        # Si pandas no está disponible, usar CSV como alternativa
        return generar_csv_transacciones(transacciones)


def generar_reporte_pdf_cliente(cliente, transacciones):
    """Genera un reporte PDF para un cliente con su historial de transacciones."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from io import BytesIO
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        
        styles = getSampleStyleSheet()
        
        # Título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0d6efd'),
            spaceAfter=30,
        )
        elements.append(Paragraph('Reporte de Cliente', title_style))
        elements.append(Spacer(1, 12))
        
        # Información del cliente
        info_data = [
            ['Nombre:', cliente.nombre_completo()],
            ['Documento:', cliente.documento],
            ['Teléfono:', cliente.telefono or 'No registrado'],
            ['Saldo Disponible:', f'€{cliente.calcular_saldo_disponible():.2f}'],
            ['Fecha Generación:', datetime.now().strftime('%d/%m/%Y %H:%M')]
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e9ecef')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 20))
        
        # Tabla de transacciones
        elements.append(Paragraph('Historial de Transacciones', styles['Heading2']))
        elements.append(Spacer(1, 12))
        
        if transacciones:
            trans_data = [['Fecha', 'Servicio', 'Monto', 'Comisión', 'Referencia']]
            
            for trans in transacciones:
                trans_data.append([
                    trans.fecha.strftime('%d/%m/%Y'),
                    trans.servicio.nombre if trans.servicio else 'N/A',
                    f'€{trans.monto:.2f}',
                    f'€{trans.comision:.2f}',
                    trans.referencia or '-'
                ])
            
            trans_table = Table(trans_data, colWidths=[1.5*inch, 2*inch, 1*inch, 1*inch, 1.5*inch])
            trans_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(trans_table)
        else:
            elements.append(Paragraph('No hay transacciones registradas.', styles['Normal']))
        
        # Generar PDF
        doc.build(elements)
        buffer.seek(0)
        
        # Crear respuesta
        response = make_response(buffer.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=reporte_{cliente.documento}_{datetime.now().strftime("%Y%m%d")}.pdf'
        response.headers['Content-Type'] = 'application/pdf'
        
        return response
        
    except ImportError:
        # Si reportlab no está disponible, retornar None
        return None
