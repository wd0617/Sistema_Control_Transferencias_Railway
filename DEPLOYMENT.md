# Guía de Deployment a PythonAnywhere

## 📋 Preparación Pre-deployment

### 1. Crear archivo .env en PythonAnywhere

Antes de subir el código, necesitas configurar las variables de entorno. **NO subas credenciales al código**.

En PythonAnywhere, crea un archivo `.env` en el directorio raíz de tu proyecto con:

```bash
SECRET_KEY=genera-una-clave-segura-aqui
DATABASE_URL=sqlite:////home/tu_usuario/Sistema_Control_Transferencias/app.db
UPLOAD_FOLDER=/home/tu_usuario/Sistema_Control_Transferencias/app/static/uploads
LIMITE_TRANSFERENCIA_SEMANAL=999
DIAS_REESTABLECIMIENTO=7
DIAS_ALERTA_VENCIMIENTO=30
```

Para generar una SECRET_KEY segura, ejecuta en tu consola local:
```python
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 🚀 Proceso de Deployment (SIN perder datos)

### Paso 1: Backup de la Base de Datos Actual

**MUY IMPORTANTE:** Antes de hacer cambios, haz backup de tu base de datos actual.

En la consola de PythonAnywhere:

```bash
cd ~/Sistema_Control_Transferencias
# Hacer copia de seguridad
cp app.db app.db.backup_$(date +%Y%m%d_%H%M%S)
```

### Paso 2: Subir el Código Nuevo

Opción A - Usando Git (recomendado):
```bash
cd ~/Sistema_Control_Transferencias
git pull origin main
```

Opción B - Subir archivos manualmente:
1. Ve a "Files" en PythonAnywhere
2. Sube los archivos nuevos a tu directorio
3. O usa `scp` desde tu computadora local

### Paso 3: Instalar Nuevas Dependencias

En la consola de PythonAnywhere:

```bash
cd ~/Sistema_Control_Transferencias
pip install --user -r requirements.txt
```

**Nota:** Algunas dependencias como `pandas`, `openpyxl` y `reportlab` pueden tardar en instalarse.

### Paso 4: Ejecutar Migraciones de Base de Datos

Las migraciones agregarán la nueva tabla `documentos_cliente` SIN afectar tus datos existentes.

```bash
cd ~/Sistema_Control_Transferencias

# Inicializar migraciones si es la primera vez
flask db init  # Solo si no existe la carpeta migrations/

# Crear migración automática
flask db migrate -m "Agregar tabla documentos_cliente"

# Revisar el archivo de migración generado en migrations/versions/
# Asegúrate de que solo crea la nueva tabla

# Aplicar migración
flask db upgrade
```

**IMPORTANTE:** Antes de ejecutar `flask db upgrade`, revisa el archivo de migración generado para asegurarte de que:
- Solo crea la tabla `documentos_cliente`
- NO modifica tablas existentes
- NO elimina datos

### Paso 5: Actualizar Código WSGI

Edita tu archivo `wsgi.py` (o el archivo de configuración web):

```python
import sys
import os

# Ruta a tu proyecto
project_home = '/home/tu_usuario/Sistema_Control_Transferencias'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv(os.path.join(project_home, '.env'))

# Importar la aplicación
from app import create_app
application = create_app()
```

### Paso 6: Reiniciar la Aplicación

En la pestaña "Web" de PythonAnywhere:
1. Click en el botón verde "Reload tu_usuario.pythonanywhere.com"
2. Espera unos segundos

### Paso 7: Verificar que Todo Funciona

1. Accede a tu sitio web
2. Inicia sesión
3. Verifica que:
   - ✅ Los clientes existentes siguen ahí
   - ✅ Las transacciones existentes están intactas
   - ✅ Puedes acceder a "Documentos" en el menú
   - ✅ Puedes acceder a "Datos" (import/export)
   - ✅ El dashboard muestra las nuevas secciones

---

## 🔍 Verificación Post-Deployment

### Verifica la estructura de la base de datos:

```bash
cd ~/Sistema_Control_Transferencias
sqlite3 app.db

# Dentro de sqlite3:
.tables  # Debe mostrar la nueva tabla documentos_cliente
.schema documentos_cliente  # Muestra la estructura
SELECT COUNT(*) FROM clientes;  # Verifica que tus clientes siguen ahí
SELECT COUNT(*) FROM transacciones;  # Verifica las transacciones
.quit
```

---

## 🐛 Solución de Problemas

### Error: "ImportError: No module named dotenv"
```bash
pip install --user python-dotenv
```

### Error: "No such table: documentos_cliente"
Ejecuta las migraciones:
```bash
flask db upgrade
```

### Error al importar/exportar Excel
Si `pandas` o `openpyxl` no se instalan correctamente en PythonAnywhere (por limitaciones de memoria), las exportaciones volverán automáticamente a CSV.

### Los datos desaparecieron
**No entres en pánico:**
1. Restaura el backup:
   ```bash
   cp app.db.backup_FECHA app.db
   ```
2. Reinicia la aplicación
3. Contacta para ayuda

---

## 📊 Funcionalidades Nuevas Disponibles

### 1. Gestión de Documentos
- Menú → Documentos
- Registrar documentos de identidad
- Alertas automáticas de vencimiento
- Verificación antes de transacciones

### 2. Importación/Exportación
- Menú → Datos
- Exportar clientes a CSV/Excel
- Exportar transacciones a CSV/Excel
- Importar clientes desde CSV
- Generar reportes PDF individuales

### 3. Dashboard Mejorado
- Alerta de documentos vencidos
- Acceso rápido a import/export
- Estadísticas de documentos

---

## 🔐 Seguridad

**IMPORTANTE:** Las credenciales ahora están en el archivo `.env` que NO debe subirse a Git.

Asegúrate de que `.env` está en tu `.gitignore`:

```bash
# Agregar al .gitignore si no está
echo ".env" >> .gitignore
```

---

## 📝 Notas Finales

- El sistema sigue funcionando con SQLite (más confiable en PythonAnywhere)
- Todas las rutas antiguas siguen funcionando
- No se eliminó ninguna funcionalidad existente
- Los datos existentes están 100% seguros
- Solo se agregaron nuevas tablas y funcionalidades

**Soporte:** Si encuentras algún problema durante el deployment, no dudes en contactar.
