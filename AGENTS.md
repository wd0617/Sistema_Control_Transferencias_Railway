# AGENTS.md — Guía para agentes de IA

Este documento describe el proyecto para cualquier agente de IA que trabaje en este repositorio. El idioma principal del proyecto (código, comentarios, mensajes al usuario y documentación) es **español**; respétalo al editar código o escribir commits.

---

## 1. Descripción general

**Sistema de Control de Transferencias Monetarias**: plataforma web **multi-negocio** (Flask). Cada negocio (tenant) tiene sus datos aislados en la misma base de datos mediante `negocio_id`. Un negocio nuevo **solicita acceso** desde `/solicitar-acceso` y el **superadmin** (dueño de la plataforma) lo aprueba, rechaza o suspende desde `/admin/negocios`. Funcionalidad por negocio:

- **Clientes**: registro, búsqueda, historial y control de límite semanal de transferencias (por defecto 999 € en ventana móvil de 7 días).
- **Transferencias**: registro de envíos por servicio (Western Union, MoneyGram, Ria, Mondial, Monty…), con comisión calculada automáticamente por porcentaje del servicio.
- **Documentos de identidad**: registro de NIE/DNI/Pasaporte por cliente con fotos (anverso/reverso), estados automáticos (vigente / por_vencer / vencido) y alertas de vencimiento (30 días por defecto).
- **Productos**: inventario sencillo (entradas/ventas, stock por unidad o por peso en kg, dashboard de ventas).
- **Importación/Exportación**: clientes y transacciones a CSV/Excel/PDF; importación masiva de clientes desde CSV con validación.
- **Notificaciones**: alertas internas (recordatorios, límites, clientes que pueden volver a enviar).
- **Extensión de Chrome** (carpeta `extension/`): captura el texto de recibos de WU/MG/Ria/Mondial/Monty y lo envía a los endpoints `/transacciones/api/*` para pre-llenar el "Registro Rápido". La URL del sistema se configura por usuario desde el popup.

No es una API pública: es una app de gestión con autenticación y tres niveles de acceso: **superadmin** (plataforma), **admin** (de su negocio) y **usuario** (de su negocio).

---

## 2. Stack tecnológico

- **Python 3.13** (`.python-version`: 3.13.13; funciona desde 3.8+)
- **Flask 2.3+** con patrón *application factory* (`create_app`)
- **Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0** — ORM
- **Flask-Migrate (Alembic)** — migraciones (carpeta `migrations/`)
- **Flask-Login** — sesiones y autenticación
- **Flask-WTF (CSRFProtect)** — protección CSRF en formularios
- **flask-cors** — CORS abierto solo para rutas `/api/*`
- **Bases de datos soportadas**: SQLite (desarrollo local, `db/sistema_transferencias.db`), MySQL vía PyMySQL (PythonAnywhere), PostgreSQL vía psycopg2-binary (Railway / Neon)
- **Servidor WSGI**: gunicorn (ver `Procfile`)
- **Opcionales con degradación elegante**: pandas + openpyxl (Excel, si fallan se exporta CSV), reportlab (PDF), Pillow (imágenes), cloudinary (fotos de productos en la nube)
- **Frontend**: Jinja2 + Bootstrap 5 + Font Awesome 6 (sin build de JS; plantillas en `app/templates/`, estáticos en `app/static/`)
- **Extensión Chrome**: Manifest V3, JavaScript plano (sin build)

No hay `pyproject.toml` ni `package.json`: las dependencias se gestionan solo con `requirements.txt`.

---

## 3. Comandos esenciales

```bash
# Entorno (Windows)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Configuración: copiar plantilla y editar
cp .env.example .env

# Inicializar BD con datos de prueba (usuarios admin/admin123 y usuario/usuario123)
python init_db.py

# Ejecutar en desarrollo (http://localhost:5000, debug=True)
python run.py

# Migraciones (Alembic vía Flask-Migrate)
flask db migrate -m "Descripción"
flask db upgrade
flask db downgrade
```

**Pruebas**: no existe suite de tests automatizados en el repositorio. La verificación es manual (ejecutar la app y probar los flujos). Si añades tests, indícalo explícitamente porque sería una convención nueva.

**Scripts auxiliares** (carpeta `scripts/`, para migración de datos SQLite → PostgreSQL/Neon):
- `scripts/export_data.py` — exporta SQLite a JSON
- `scripts/import_to_postgres.py` — importa el JSON a PostgreSQL
- `scripts/verify_neon.py` — verifica la conexión a Neon

---

## 4. Estructura del código

```
├── run.py / app.py          # Puntos de entrada idénticos: create_app() + app.run(debug=True)
├── config.py                # Clase Config: lee .env y define toda la configuración
├── init_db.py               # Crea tablas y puebla datos de prueba (idempotente)
├── Procfile                 # release: flask db upgrade · web: gunicorn ... "app:create_app()"
├── webapp_pythonanywhere_com_wsgi.py  # WSGI de ejemplo para PythonAnywhere
├── app/
│   ├── __init__.py          # create_app(): init extensiones, blueprints, context processors,
│   │                        #   filtros Jinja (smart_float, smart_money), create_all + upgrade + ALTERs de fallback
│   ├── extensions.py        # db, login_manager, migrate, csrf (instancias sin app)
│   ├── decorators.py        # @admin_required
│   ├── models/              # Un archivo por dominio:
│   │   ├── negocio.py       #   Negocio (tenant): estados pendiente/aprobado/rechazado/suspendido
│   │   ├── cliente.py       #   Cliente, Servicio (tabla M2M cliente_servicio)
│   │   ├── transaccion.py   #   Transaccion, Notificacion
│   │   ├── user.py          #   User (Flask-Login: is_admin, is_superadmin, activo, negocio_id), ActivityLog, load_user
│   │   ├── documento.py     #   DocumentoCliente (vencimientos, estados, contadores)
│   │   └── producto.py      #   Producto, MovimientoProducto (inventario)
│   ├── routes/              # Blueprints registrados con url_prefix en create_app:
│   │   ├── auth.py          #   login/logout/perfil (bloquea usuarios inactivos y negocios no aprobados)
│   │   ├── registro.py      #   /solicitar-acceso — solicitud pública de acceso (crea Negocio pendiente + User inactivo)
│   │   ├── admin.py         #   /admin — panel superadmin (negocios, aprobar/suspender, modo soporte)
│   │   │                    #     + gestión de usuarios del negocio (admin de negocio)
│   │   ├── main.py          #   dashboard (/)
│   │   ├── clientes.py      #   /clientes — CRUD
│   │   ├── transacciones.py #   /transacciones — CRUD + registro-rapido + API:
│   │   │                    #     GET /api/buscar-cliente, POST /api/analizar-recibo
│   │   ├── servicios.py     #   /servicios — CRUD (admin)
│   │   ├── calculadora.py   #   /calculadora — comisiones (AJAX, exento de CSRF)
│   │   ├── documentos.py    #   /documentos — CRUD + alertas de vencimiento
│   │   ├── data_management.py # /datos — importar/exportar CSV/Excel/PDF
│   │   ├── notificaciones.py  # /notificaciones
│   │   └── productos.py     #   /productos — inventario, entradas/ventas, dashboard
│   ├── utils/
│   │   ├── tenancy.py       #   Multitenancy: current_negocio_id(), query_negocio(), get_negocio_o_404(),
│   │   │                    #     listener before_insert que estampa negocio_id
│   │   ├── telegram.py      #   Avisos al dueño por Telegram (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)
│   │   ├── cliente_utils.py #   Lógica de límites semanales y visitas
│   │   ├── export_utils.py / import_utils.py  # CSV/Excel/PDF
│   │   ├── notificaciones.py#   contar_notificaciones_pendientes() (context processor)
│   │   └── parse_recibo.py  #   Parser regex de recibos (WU, MoneyGram, Ria, Mondial, Monty)
│   ├── templates/           # Jinja2: base.html + una subcarpeta por blueprint
│   └── static/              # css, js, img, uploads (fotos de documentos/productos)
├── extension/               # Extensión Chrome MV3 (content.js captura recibos, popup.js envía)
├── db/                      # SQLite local (sistema_transferencias.db)
├── migrations/              # Alembic (versions/ con las migraciones aplicadas)
├── scripts/                 # Migración de datos a PostgreSQL/Neon
└── DEPLOYMENT.md / NEON_SETUP.md / RAILWAY_SETUP.md / RESUMEN_MEJORAS.md  # Docs operativas
```

---

## 5. Configuración y entorno

Todo se configura por variables de entorno (cargadas desde `.env` con python-dotenv en `config.py`). Ver `.env.example`:

- `SECRET_KEY` — obligatoria en producción (si falta se genera una aleatoria, lo que invalida sesiones en cada reinicio).
- `DATABASE_URL` — si existe, tiene prioridad. Se normaliza `postgres://` → `postgresql://` y se añade `sslmode=require` automáticamente para hosts `neon.tech`. Sin `DATABASE_URL`: SQLite en `db/sistema_transferencias.db` (local) o `~/Sistema_Control_Transferencias/app.db` si `PYTHONANYWHERE_SITE` está definida.
- `UPLOAD_FOLDER` (por defecto `app/static/uploads`), `MAX_CONTENT_LENGTH` (16 MB), extensiones permitidas: png/jpg/jpeg/gif/pdf.
- `LIMITE_TRANSFERENCIA_SEMANAL` (999), `DIAS_REESTABLECIMIENTO` (7), `DIAS_ALERTA_VENCIMIENTO` (30).
- `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` — opcionales; si están las tres, se configura Cloudinary (fotos de productos).
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — opcionales; avisan al dueño por Telegram cuando llega una solicitud de acceso nueva. Sin ellas, los avisos se omiten silenciosamente.

Pool de conexiones configurado en `config.py` (`pool_pre_ping`, `pool_recycle=280`) porque PythonAnywhere corta conexiones inactivas a los ~300 s.

---

## 6. Convenciones del código

- **Idioma**: español en nombres de modelos/rutas/templates, comentarios, docstrings, mensajes flash y commits. El código de la extensión usa español rioplatense en su README.
- **Modelos**: `db.Model` con `__tablename__` plural en español; timestamps con `datetime.utcnow`; lógica de negocio en properties/métodos del modelo (p. ej. `DocumentoCliente.actualizar_estado`, `Cliente.calcular_saldo_disponible`).
- **Import del ORM**: los modelos importan `from app import db` (o `from app.extensions import db`); las rutas importan los modelos desde `app.models.*`.
- **Rutas**: un Blueprint por módulo, registrado en `create_app()` con `url_prefix`. Autenticación con `@login_required`; acciones restringidas con `@admin_required` (`app/decorators.py`).
- **Formularios**: HTML + POST tradicional con CSRF (Flask-WTF). Excepciones: la calculadora AJAX está exenta de CSRF (`csrf.exempt` en `create_app`) y los endpoints `/transacciones/api/*` consumidos por la extensión usan la sesión del navegador.
- **Consultas**: se prefieren agregaciones SQL directas (`func.count`, `func.coalesce(func.sum(...))`) y `joinedload`/paginación (50 por página) en listados, en lugar de cargar objetos completos.
- **Templates**: heredan de `base.html`; filtros disponibles `smart_float` y `smart_money` (números limpios, sufijo €); context processors inyectan `notificaciones_count` y `now` en todos los templates.
- **Dependencias opcionales**: importar siempre de forma defensiva (try/except) y degradar a CSV cuando pandas/reportlab no estén disponibles, siguiendo el patrón de `app/utils/export_utils.py`.

---

## 6.1 Multitenancy (regla crítica)

La BD es compartida y el aislamiento es por `negocio_id`. Toda tabla de dominio (`clientes`, `servicios`, `transacciones`, `documentos_cliente`, `notificaciones`, `productos`, `movimientos_producto`) tiene esa columna. `users` y `activity_logs` NO son tenant (un usuario cuelga de un negocio, salvo el superadmin que tiene `negocio_id=NULL`).

**Regla de oro al tocar consultas** (helpers en `app/utils/tenancy.py`):

- `Modelo.query...` sobre modelos tenant → `query_negocio(Modelo)...` (filtra por el negocio actual; sin filtro solo si el superadmin no está en modo soporte).
- `Modelo.query.get_or_404(id)` → `get_negocio_o_404(Modelo, id)` (404 si el registro es de otro negocio).
- Agregados `db.session.query(func...)` globales → añadir `.filter(Modelo.negocio_id == nid)` cuando `nid = current_negocio_id()` no es None.
- Al **crear** registros no hace falta estampar el negocio: un listener `before_insert` lo hace automáticamente (registrado en `create_app`). Fuera de contexto de request (scripts/seeds) hay que asignarlo a mano.

Roles y flujo de acceso:

- **superadmin** (`User.is_superadmin`, sin negocio): panel `/admin/negocios` (aprobar/rechazar/suspender/reactivar, notas internas, fichas con métricas) y **modo soporte** (`session['negocio_vista']`): navega la app como un negocio concreto, con banner visible. Decorador `@superadmin_required`.
- **admin de negocio** (`User.is_admin`): gestiona servicios, datos y los usuarios de su negocio (`/admin/usuarios`). `@admin_required` también deja pasar al superadmin.
- **usuario**: operativa diaria.
- Solicitud pública en `/solicitar-acceso` (blueprint `registro`): crea `Negocio(pendiente)` + `User(admin, activo=False)` y avisa por Telegram. El login (`auth.login` y `load_user`) bloquea usuarios inactivos y negocios no aprobados con mensajes según el estado. Al aprobar se crean servicios semilla (WU, Mondial, Monty, Moneygram, Ria).
- Unicidad por negocio: `clientes.documento` y `servicios.nombre` son únicos por `(negocio_id, valor)`, no globales. `users.username`/`email` siguen siendo globales.

---

## 7. Base de datos y migraciones

Tablas: `negocios`, `users`, `activity_logs`, `clientes`, `servicios`, `cliente_servicio` (M2M), `transacciones`, `documentos_cliente`, `notificaciones`, `productos`, `movimientos_producto`.

Al arrancar, `create_app()` hace tres cosas en este orden (`app/__init__.py`):

1. `db.create_all()` — crea tablas nuevas.
2. `flask_migrate.upgrade()` en try/except — aplica migraciones Alembic pendientes.
3. ALTER TABLE de fallback en try/except — añade columnas nuevas si la BD ya existía sin ellas.

Consecuencia práctica: el arranque es autocurativo, pero **los cambios de esquema deben generar también su migración Alembic** (`flask db migrate`) para producción. No confíes solo en el fallback. Como `create_all` corre antes que `upgrade`, las migraciones deben ser **defensivas** (comprobar tablas/columnas/constraints existentes antes de crearlas); ver `migrations/versions/b7f3a21c9d04_multitenancy_negocios.py` como patrón de referencia.

---

## 8. Deployment

Tres destinos documentados (ver los `.md` correspondientes):

- **PythonAnywhere** (`DEPLOYMENT.md`, `webapp_pythonanywhere_com_wsgi.py`): SQLite o MySQL, WSGI apuntando a `run:app`. Hacer backup de la BD antes de actualizar.
- **Railway** (`RAILWAY_SETUP.md`, `Procfile`): detecta Python automáticamente; `release: flask db upgrade`, `web: gunicorn -w 2 -b 0.0.0.0:$PORT "app:create_app()"`. PostgreSQL provisionado por Railway.
- **Neon** (`NEON_SETUP.md`, `scripts/`): solo como BD PostgreSQL externa; la app corre en otro host. `config.py` fuerza SSL automáticamente.

La URL de producción de Railway es el valor por defecto (`DEFAULT_BASE_URL`) en `extension/popup.js`. La extensión permite configurar la URL por usuario desde el popup (guardada en `chrome.storage.sync`).

**Multi-negocio**: la vía principal es la plataforma multitenant descrita en §6.1 (una sola instancia, aislamiento por `negocio_id`, aprobación manual). El despliegue de **instancias separadas por negocio** (`MULTITENANT_INSTANCIAS.md`) queda como alternativa para casos que requieran aislamiento físico total de datos.

---

## 9. Seguridad

- Nunca subir `.env` ni credenciales al repositorio (está en `.gitignore`); usar `.env.example` como plantilla.
- Cambiar las credenciales por defecto (`admin`/`admin123`) creadas por `init_db.py` en cualquier entorno real.
- Contraseñas con hash Werkzeug (`generate_password_hash`); sesiones con Flask-Login; CSRF activo salvo exenciones explícitas listadas en `app/__init__.py`.
- CORS está abierto (`origins: *`) para `/api/*` — tenlo en cuenta al añadir endpoints nuevos bajo ese prefijo.
- Validar archivos subidos contra `ALLOWED_EXTENSIONS` y respetar `MAX_CONTENT_LENGTH`.
- `ActivityLog` registra acciones de usuarios; mantener el registro al añadir acciones sensibles.
- **Nota**: `run.py`/`app.py` ejecutan con `debug=True`; no usar ese modo en producción (usar gunicorn según el `Procfile`).
