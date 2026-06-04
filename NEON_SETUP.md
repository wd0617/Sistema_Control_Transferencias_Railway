# Configuración con Neon PostgreSQL

Esta guía te permite usar **Neon** como base de datos PostgreSQL para el Sistema de Control de Transferencias.

> ⚠️ **Importante**: Neon es **solo la base de datos**. La aplicación Flask debe seguir corriendo en otro servidor (Render, PythonAnywhere, VPS, etc.).

---

## 1. Crear una base de datos en Neon

1. Ve a [https://neon.tech](https://neon.tech) y crea una cuenta gratuita.
2. Crea un nuevo proyecto.
3. Crea una base de datos (por ejemplo: `sistema_transferencias`).
4. Ve a la sección **Connection Details** y copia la URL de conexión. Tendrá este formato:
   ```
   postgresql://usuario:password@host.neon.tech/basedatos?sslmode=require
   ```

---

## 2. Configurar la variable de entorno

En tu servidor (o localmente para probar), configura la variable `DATABASE_URL`:

### Linux / macOS
```bash
export DATABASE_URL='postgresql://usuario:password@host.neon.tech/sistema_transferencias?sslmode=require'
```

### Windows (PowerShell)
```powershell
$env:DATABASE_URL="postgresql://usuario:password@host.neon.tech/sistema_transferencias?sslmode=require"
```

### Windows (CMD)
```cmd
set DATABASE_URL=postgresql://usuario:password@host.neon.tech/sistema_transferencias?sslmode=require
```

### Archivo .env (recomendado para local)
Crea o edita el archivo `.env` en la raíz del proyecto:
```env
DATABASE_URL=postgresql://usuario:password@host.neon.tech/sistema_transferencias?sslmode=require
SECRET_KEY=tu_clave_secreta_segura_aqui
```

---

## 3. Verificar la conexión

Ejecuta el script de verificación:

```bash
python scripts/verify_neon.py
```

Si todo está bien, verás:
```
✅ Conexión exitosa a PostgreSQL
📦 Versión: PostgreSQL 15.x on x86_64-pc-linux-gnu, compiled by gcc ...
```

---

## 4. Crear las tablas e inicializar datos

### Opción A: Usar Flask-Migrate (recomendado para producción)

```bash
# Generar migración inicial
flask db migrate -m "Initial migration"

# Aplicar migración
flask db upgrade
```

### Opción B: Usar db.create_all() (más rápido para empezar)

```bash
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all(); print('Tablas creadas')"
```

### Poblar datos de prueba (opcional)

```bash
python init_db.py
```

> Nota: `init_db.py` creará las tablas automáticamente si no existen y luego insertará datos de prueba.

---

## 5. Ejecutar la aplicación

```bash
python run.py
```

O con Gunicorn (para producción):

```bash
gunicorn -w 2 -b 0.0.0.0:8000 "app:create_app()"
```

---

## 6. Desplegar la app (elegir uno)

### Opción A: Render + Neon (recomendado)
- Despliega la app Flask en [Render](https://render.com)
- En las variables de entorno de Render, agrega `DATABASE_URL` apuntando a Neon
- Render ejecutará la app y Neon manejará la base de datos

### Opción B: PythonAnywhere + Neon
- Sube tu código a PythonAnywhere como siempre
- En el archivo WSGI, asegúrate de que `DATABASE_URL` esté configurada
- En PythonAnywhere puedes setear variables de entorno desde la consola o hardcodear temporalmente en `config.py`

---

## Notas importantes

- **SSL obligatorio**: Neon requiere conexiones SSL. El `config.py` automáticamente agrega `sslmode=require` si detecta `neon.tech` en la URL, pero es mejor que lo incluyas manualmente en tu `DATABASE_URL`.
- **IP permitidas**: En el panel de Neon, verifica que tu servidor de aplicaciones esté permitido para conectarse (Neon puede requerir configuración de IPs permitidas).
- **No borres SQLite todavía**: Puedes alternar entre SQLite (desarrollo local) y PostgreSQL (producción) simplemente cambiando la variable `DATABASE_URL`.
