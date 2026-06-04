"""
Exporta todos los datos de la base de datos actual (SQLite/MySQL) a archivos JSON.
Uso:
    python scripts/export_data.py
Genera archivos en la carpeta migrations/data/:
    - users.json
    - clientes.json
    - servicios.json
    - transacciones.json
    - documentos.json
    - notificaciones.json
"""

import os
import sys
import json
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.user import User, ActivityLog
from app.models.cliente import Cliente, Servicio
from app.models.transaccion import Transaccion, Notificacion
from app.models.documento import DocumentoCliente

def json_serial(obj):
    """Serializador JSON para fechas."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def export_table(query, filename, extra_fields=None):
    """Exporta una query SQLAlchemy a JSON."""
    os.makedirs('migrations/data', exist_ok=True)
    rows = query.all()
    data = []
    
    for row in rows:
        item = {c.name: getattr(row, c.name) for c in row.__table__.columns}
        if extra_fields:
            for key, getter in extra_fields.items():
                try:
                    item[key] = getter(row)
                except:
                    item[key] = None
        data.append(item)
    
    path = os.path.join('migrations/data', filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=json_serial)
    
    print(f"✅ Exportado: {filename} ({len(data)} registros)")
    return len(data)

def main():
    app = create_app()
    with app.app_context():
        print("📦 Exportando datos de la base de datos actual...")
        print(f"   URI: {app.config['SQLALCHEMY_DATABASE_URI'][:60]}...")
        print("-" * 50)
        
        total = 0
        total += export_table(User.query, 'users.json')
        total += export_table(ActivityLog.query, 'activity_logs.json')
        total += export_table(Servicio.query, 'servicios.json')
        
        # Clientes: necesitamos exportar los IDs de servicios relacionados
        clientes_data = []
        for c in Cliente.query.all():
            item = {col.name: getattr(c, col.name) for col in c.__table__.columns}
            item['servicios_ids'] = [s.id for s in c.servicios]
            clientes_data.append(item)
        
        with open('migrations/data/clientes.json', 'w', encoding='utf-8') as f:
            json.dump(clientes_data, f, ensure_ascii=False, indent=2, default=json_serial)
        print(f"✅ Exportado: clientes.json ({len(clientes_data)} registros)")
        total += len(clientes_data)
        
        total += export_table(Transaccion.query, 'transacciones.json')
        total += export_table(Notificacion.query, 'notificaciones.json')
        total += export_table(DocumentoCliente.query, 'documentos.json')
        
        print("-" * 50)
        print(f"🎉 Exportación completa: {total} registros totales")
        print("   Archivos en: migrations/data/")

if __name__ == '__main__':
    main()
