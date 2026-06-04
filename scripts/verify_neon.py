"""
Script para verificar la conexión a Neon PostgreSQL.
Uso:
    python scripts/verify_neon.py
Requiere la variable de entorno DATABASE_URL configurada.
"""

import os
import sys

# Asegurar que el directorio raíz está en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text

def verify_connection():
    app = create_app()
    
    with app.app_context():
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        print(f"URI configurada: {db_uri}")
        print("-" * 50)
        
        try:
            # Probar conexión ejecutando una consulta simple
            result = db.session.execute(text("SELECT version();"))
            version = result.scalar()
            print(f"✅ Conexión exitosa a PostgreSQL")
            print(f"📦 Versión: {version}")
            print("-" * 50)
            
            # Verificar tablas existentes
            result = db.session.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
            ))
            tables = [row[0] for row in result]
            
            if tables:
                print(f"📋 Tablas encontradas ({len(tables)}):")
                for t in tables:
                    print(f"   - {t}")
            else:
                print("⚠️  No hay tablas creadas todavía.")
                print("   Ejecuta: python init_db.py")
            
            return True
            
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
            print("\n💡 Posibles soluciones:")
            print("   1. Verifica que DATABASE_URL esté configurada correctamente")
            print("   2. Asegúrate de incluir '?sslmode=require' al final de la URL de Neon")
            print("   3. Verifica que la IP desde donde te conectas esté en la lista de permitidas de Neon")
            return False

if __name__ == '__main__':
    if not os.environ.get('DATABASE_URL'):
        print("❌ ERROR: La variable de entorno DATABASE_URL no está configurada.")
        print("\nEjemplo:")
        print("   export DATABASE_URL='postgresql://usuario:password@host.neon.tech/basedatos?sslmode=require'")
        sys.exit(1)
    
    success = verify_connection()
    sys.exit(0 if success else 1)
