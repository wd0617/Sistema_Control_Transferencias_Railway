"""
Importa datos desde archivos JSON (generados por export_data.py) a PostgreSQL.
Uso:
    export DATABASE_URL='postgresql://...'
    python scripts/import_to_postgres.py
Requiere que las tablas ya existan (ejecutar primero: flask db upgrade o db.create_all()).
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.user import User
from app.models.cliente import Cliente, Servicio
from app.models.transaccion import Transaccion, Notificacion
from app.models.documento import DocumentoCliente

def parse_date(value):
    """Convierte string ISO a datetime/date."""
    if not value:
        return None
    if isinstance(value, str):
        if 'T' in value:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        else:
            return datetime.strptime(value, '%Y-%m-%d').date()
    return value

def load_json(filename):
    path = os.path.join('migrations/data', filename)
    if not os.path.exists(path):
        print(f"⚠️  No existe: {path}")
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def import_servicios():
    data = load_json('servicios.json')
    if not data:
        return 0
    
    # Mapear IDs antiguos a nuevos
    id_map = {}
    for item in data:
        old_id = item.pop('id', None)
        s = Servicio(**item)
        db.session.add(s)
        db.session.flush()
        id_map[old_id] = s.id
    
    db.session.commit()
    print(f"✅ Servicios importados: {len(data)}")
    return id_map

def import_users():
    data = load_json('users.json')
    if not data:
        return {}
    
    id_map = {}
    for item in data:
        old_id = item.pop('id', None)
        item['created_at'] = parse_date(item.get('created_at'))
        item['last_login'] = parse_date(item.get('last_login'))
        u = User(**item)
        db.session.add(u)
        db.session.flush()
        id_map[old_id] = u.id
    
    db.session.commit()
    print(f"✅ Usuarios importados: {len(data)}")
    return id_map

def import_clientes(servicio_id_map):
    data = load_json('clientes.json')
    if not data:
        return {}
    
    id_map = {}
    for item in data:
        servicios_ids = item.pop('servicios_ids', [])
        old_id = item.pop('id', None)
        
        item['fecha_nacimiento'] = parse_date(item.get('fecha_nacimiento'))
        item['fecha_registro'] = parse_date(item.get('fecha_registro'))
        item['ultima_visita'] = parse_date(item.get('ultima_visita'))
        item['documento_fecha_emision'] = parse_date(item.get('documento_fecha_emision'))
        item['documento_fecha_vencimiento'] = parse_date(item.get('documento_fecha_vencimiento'))
        
        c = Cliente(**item)
        db.session.add(c)
        db.session.flush()
        id_map[old_id] = c.id
        
        # Restaurar relaciones con servicios
        for sid in servicios_ids:
            nuevo_sid = servicio_id_map.get(sid)
            if nuevo_sid:
                servicio = Servicio.query.get(nuevo_sid)
                if servicio:
                    c.servicios.append(servicio)
    
    db.session.commit()
    print(f"✅ Clientes importados: {len(data)}")
    return id_map

def import_transacciones(cliente_id_map, servicio_id_map, user_id_map):
    data = load_json('transacciones.json')
    if not data:
        return 0
    
    for item in data:
        item.pop('id', None)
        item['fecha'] = parse_date(item.get('fecha'))
        # Mapear FKs
        old_cliente = item.get('cliente_id')
        old_servicio = item.get('servicio_id')
        old_creado_por = item.get('creado_por')
        
        item['cliente_id'] = cliente_id_map.get(old_cliente)
        item['servicio_id'] = servicio_id_map.get(old_servicio)
        item['creado_por'] = user_id_map.get(old_creado_por) if old_creado_por else None
        
        if item['cliente_id'] and item['servicio_id']:
            t = Transaccion(**item)
            db.session.add(t)
    
    db.session.commit()
    print(f"✅ Transacciones importadas: {len(data)}")
    return len(data)

def import_notificaciones(cliente_id_map):
    data = load_json('notificaciones.json')
    if not data:
        return 0
    
    for item in data:
        item.pop('id', None)
        item['fecha_creacion'] = parse_date(item.get('fecha_creacion'))
        item['fecha_lectura'] = parse_date(item.get('fecha_lectura'))
        old_cliente = item.get('cliente_id')
        item['cliente_id'] = cliente_id_map.get(old_cliente)
        
        if item['cliente_id']:
            n = Notificacion(**item)
            db.session.add(n)
    
    db.session.commit()
    print(f"✅ Notificaciones importadas: {len(data)}")
    return len(data)

def import_documentos(cliente_id_map, user_id_map):
    data = load_json('documentos.json')
    if not data:
        return 0
    
    for item in data:
        item.pop('id', None)
        item['fecha_emision'] = parse_date(item.get('fecha_emision'))
        item['fecha_vencimiento'] = parse_date(item.get('fecha_vencimiento'))
        item['fecha_registro'] = parse_date(item.get('fecha_registro'))
        item['fecha_actualizacion'] = parse_date(item.get('fecha_actualizacion'))
        
        old_cliente = item.get('cliente_id')
        old_actualizado = item.get('actualizado_por')
        item['cliente_id'] = cliente_id_map.get(old_cliente)
        item['actualizado_por'] = user_id_map.get(old_actualizado) if old_actualizado else None
        
        if item['cliente_id']:
            d = DocumentoCliente(**item)
            db.session.add(d)
    
    db.session.commit()
    print(f"✅ Documentos importados: {len(data)}")
    return len(data)

def main():
    app = create_app()
    with app.app_context():
        print("📥 Importando datos a PostgreSQL...")
        print(f"   URI: {app.config['SQLALCHEMY_DATABASE_URI'][:60]}...")
        print("-" * 50)
        
        # Limpiar tablas en orden (respetando FKs)
        print("🧹 Limpiando tablas existentes...")
        db.session.query(DocumentoCliente).delete(synchronize_session=False)
        db.session.query(Notificacion).delete(synchronize_session=False)
        db.session.query(Transaccion).delete(synchronize_session=False)
        db.session.query(Cliente).delete(synchronize_session=False)
        db.session.query(Servicio).delete(synchronize_session=False)
        db.session.query(User).delete(synchronize_session=False)
        db.session.commit()
        
        # Importar en orden correcto
        servicio_map = import_servicios()
        user_map = import_users()
        cliente_map = import_clientes(servicio_map)
        import_transacciones(cliente_map, servicio_map, user_map)
        import_notificaciones(cliente_map)
        import_documentos(cliente_map, user_map)
        
        print("-" * 50)
        print("🎉 Importación completa!")
        print("   Asegúrate de reiniciar la app para limpiar sesiones.")

if __name__ == '__main__':
    main()
