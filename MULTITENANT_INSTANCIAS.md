# Multitenancy por instancias separadas (1 instancia = 1 negocio)

> **Nota (legacy)**: desde la versión multitenant, la vía principal es UNA sola instancia
> con aislamiento por `negocio_id` y aprobación de negocios desde `/admin/negocios`
> (ver `AGENTS.md` §6.1). Este documento queda como alternativa para negocios que
> requieran aislamiento físico total (base de datos y despliegue propios).

Esta aplicación puede desplegarse también en modo **una instancia por negocio**, cada una con su propia base de datos PostgreSQL. Todas las instancias salen del mismo repositorio, así que un solo `git push` las actualiza a la vez (Railway hace redeploy automático en cada proyecto conectado).

Ventajas de este enfoque:

- Aislamiento total de datos entre negocios (ni siquiera comparten tablas).
- Cero cambios en modelos, rutas ni migraciones.
- Se puede escalar o migrar un negocio sin tocar a los demás.

Costos a tener en cuenta:

- Cada negocio consume su propio proyecto/recursos en Railway.
- Los usuarios y servicios se administran por separado en cada instancia.

---

## Checklist: dar de alta un negocio nuevo

### 1. Crear el proyecto en Railway

1. En el dashboard de Railway: **New Project** → **Provision PostgreSQL** (crea la BD y la variable `DATABASE_URL` automáticamente).
2. En el mismo proyecto: **New** → **GitHub Repo** → seleccionar `Sistema_Control_Transferencias`.
   - Es el **mismo repo** para todos los negocios; no hacer fork.

### 2. Variables de entorno (pestaña Variables del servicio)

| Variable | Valor |
|----------|-------|
| `SECRET_KEY` | **Única por negocio**. Generar con: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Inyectada automáticamente por Railway PostgreSQL |
| `UPLOAD_FOLDER` | `app/static/uploads` (default, opcional) |
| `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | Opcional, por negocio (fotos de productos en la nube) |
| `PYTHONANYWHERE_SITE` | **No agregar nunca** |

> Reutilizar la misma `SECRET_KEY` entre negocios permitiría que una cookie de sesión de un negocio sea válida en otro. Generar siempre una nueva.

### 3. Migraciones

El `Procfile` ya incluye `release: flask db upgrade`, así que las tablas se crean solas en el primer deploy. Verificar en **Deployments → Logs** que el release haya terminado sin errores.

### 4. Crear usuarios

Desde la Shell de Railway (Deployments → deployment activo → Shell):

```bash
python init_db.py
```

Esto crea `admin/admin123` y `usuario/usuario123`. **Cambiar estas contraseñas de inmediato** desde el perfil de usuario, o crear los usuarios reales y borrar los de prueba.

### 5. Datos iniciales (opcional)

- Los servicios de transferencia (Western Union, MoneyGram, Ria, Mondial, Monty…) se pueden crear a mano desde `/servicios` (requiere admin).
- Para sembrar datos masivamente (p. ej. cartera de clientes): `scripts/export_data.py` genera un JSON desde otra instancia/SQLite y `scripts/import_to_postgres.py` lo importa en la nueva. Ver `NEON_SETUP.md` y `RAILWAY_SETUP.md` §7 para el flujo detallado.

### 6. Uploads (fotos de documentos/productos)

El filesystem de Railway es **efímero**: sin persistencia, las fotos se pierden en cada redeploy. Elegir una opción por negocio:

- **Railway Volume**: New → Volume → montar en `/app/app/static/uploads`.
- **Cloudinary**: configurar las 3 variables `CLOUDINARY_*` (fotos de productos).

### 7. Dominio

Settings → Domains → custom domain. Lo habitual: un subdominio por negocio, p. ej. `tienda2.midominio.com`.

### 8. Extensión de Chrome

La extensión ya no lleva la URL hardcodeada como única opción: cada usuario la configura en el popup (**⚙️ Configurar URL del sistema**). Indicar al negocio la URL de **su** instancia. Ver `extension/README.md`.

---

## Operación diaria multi-negocio

- **Actualizaciones**: push a `main` → Railway redeploya todos los proyectos conectados. Las migraciones nuevas se aplican solas vía `release: flask db upgrade`.
- **Backups**: Railway no hace backups automáticos del volumen ni de la BD en el free tier; programar `pg_dump` por negocio si los datos son críticos.
- **Problemas de un negocio**: revisar logs solo de su proyecto en Railway; las instancias son independientes.
