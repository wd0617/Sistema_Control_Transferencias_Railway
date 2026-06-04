# Despliegue en Railway

Guía completa para migrar el Sistema de Control de Transferencias de PythonAnywhere a Railway.

---

## 1. Preparar el código (haz esto en tu computadora)

Asegúrate de que todos los cambios estén commiteados y subidos a GitHub:

```bash
git add .
git commit -m "Preparación para Railway: optimizaciones + PostgreSQL"
git push origin main
```

---

## 2. Crear cuenta en Railway

1. Ve a [https://railway.app](https://railway.app)
2. Regístrate con tu cuenta de GitHub
3. Verifica tu email (te dará $5 de créditos mensuales en el free tier)

---

## 3. Crear el proyecto y la base de datos

1. En el dashboard de Railway, haz clic en **"New Project"**
2. Selecciona **"Provision PostgreSQL"** → Se creará una base de datos automáticamente
3. Railway generará la variable `DATABASE_URL` automáticamente (no necesitas copiarla)

---

## 4. Desplegar la app desde GitHub

1. Dentro del proyecto, haz clic en **"New"** → **"GitHub Repo"**
2. Selecciona tu repositorio `Sistema_Control_Transferencias`
3. Railway detectará automáticamente que es Python gracias al `requirements.txt` y `Procfile`

---

## 5. Configurar variables de entorno

Ve a tu servicio de app (el que se creó del repo) → pestaña **Variables** → **New Variable**:

| Variable | Valor | ¿Obligatorio? |
|----------|-------|---------------|
| `SECRET_KEY` | Genera una clave segura con: `python -c "import secrets; print(secrets.token_hex(32))"` | ✅ Sí |
| `DATABASE_URL` | Ya está inyectada automáticamente por Railway PostgreSQL | ✅ Automático |
| `PYTHONANYWHERE_SITE` | **NO agregar** | ❌ No aplica |
| `UPLOAD_FOLDER` | `app/static/uploads` | Opcional (default) |

> **Nota:** No incluyas `FLASK_ENV=production` como variable. Railway maneja el entorno automáticamente.

---

## 6. Ejecutar migraciones

Railway desplegará la app automáticamente, pero las tablas aún no existen. Necesitas ejecutar migraciones:

### Opción A: Desde la consola de Railway (recomendada)
1. Ve a tu servicio de app en Railway
2. Ve a la pestaña **"Deployments"** → selecciona el deployment activo
3. Haz clic en **"Shell"** (o usa la pestaña **"Console"**)
4. Ejecuta:
   ```bash
   flask db upgrade
   ```
   > Si falla porque no hay migraciones generadas, ejecuta primero:
   > ```bash
   > flask db migrate -m "Initial migration"
   > flask db upgrade
   > ```

### Opción B: Crear tablas directamente
Si prefieres no usar migraciones:
```bash
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

---

## 7. Migrar datos desde PythonAnywhere

### Paso 7.1: Exportar datos de PythonAnywhere
1. Abre una consola **Bash** en PythonAnywhere
2. Ve al directorio de tu proyecto:
   ```bash
   cd /home/wd0617/Sistema_Control_Transferencias
   ```
3. Ejecuta el script de exportación:
   ```bash
   python scripts/export_data.py
   ```
4. Descarga la carpeta `migrations/data/` a tu computadora (vía SFTP o el panel de Files de PythonAnywhere)

### Paso 7.2: Subir datos a Railway
1. Sube la carpeta `migrations/data/` a tu repositorio de GitHub y haz push:
   ```bash
   git add migrations/data/
   git commit -m "Datos migrados desde PythonAnywhere"
   git push origin main
   ```
2. Railway hará redeploy automáticamente con los datos

### Paso 7.3: Importar datos en Railway
1. Ve al deployment activo en Railway
2. Abre una **Shell**
3. Ejecuta:
   ```bash
   python scripts/import_to_postgres.py
   ```

---

## 8. Verificar que todo funciona

1. Railway te dará una URL tipo `https://tusistema-production.up.railway.app`
2. Abre la URL en tu navegador
3. Prueba:
   - Login
   - Dashboard (debe cargar rápido ahora)
   - Lista de transacciones (paginada)
   - Búsqueda de clientes

---

## 9. Configurar dominio personalizado (opcional)

1. En Railway, ve a tu servicio → pestaña **Settings** → **Domains**
2. Haz clic en **"Custom Domain"**
3. Sigue las instrucciones para apuntar tu dominio

---

## ⚠️ Importante: Archivos subidos (uploads)

El filesystem de Railway es **efímero**: los archivos subidos se pierden en cada redeploy.

**Si subes fotos de documentos/DNI**, tienes 3 opciones:

### Opción A: Railway Volume (recomendada para empezar)
1. En tu proyecto Railway, haz **New** → **Volume**
2. Monta el volumen en `/app/app/static/uploads`
3. Los archivos persistirán entre reinicios

### Opción B: Supabase Storage (más escalable)
1. Crea un bucket gratuito en [Supabase](https://supabase.com)
2. Modifica el código para subir archivos allí en lugar de disco local

### Opción C: No usar uploads
Si no necesitas subir fotos de documentos, desactiva esa funcionalidad.

---

## 📋 Comparativa: PythonAnywhere vs Railway

| Característica | PythonAnywhere | Railway |
|----------------|----------------|---------|
| App + DB en uno | ❌ Separados | ✅ Misma plataforma |
| Conexiones DB | MySQL remoto (lento) | PostgreSQL local (rápido) |
| Caídas de conexión | Frecuentes | Ninguna |
| N+1 queries | Terribles | Normales |
| Precio (básico) | ~$5/mes | Free tier ($5 créditos) |
| Deploy desde Git | Manual | Automático |
| Dominio HTTPS | Configuración manual | Automático |

---

## 🆘 Solución de problemas

### "Internal Server Error" después de deploy
1. Ve a **Deployments** → selecciona el deployment → pestaña **Logs**
2. Busca el error real (probablemente falta `SECRET_KEY` o las tablas no existen)

### Las tablas no existen
Ejecuta `flask db upgrade` desde la consola de Railway.

### Los datos no aparecen
Asegúrate de ejecutar `python scripts/import_to_postgres.py` en Railway y que los archivos JSON estén en `migrations/data/`.
