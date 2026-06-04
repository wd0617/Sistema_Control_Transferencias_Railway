# Sistema de Control de Transferencias Monetarias

Sistema web completo para gestión de clientes, transferencias, documentos y control de límites semanales.

## 🚀 Características

### ✅ Gestión de Clientes
- Registro completo de clientes
- Búsqueda y filtrado
- Historial de visitas
- Control de límites semanales (€999)

### 📄 Gestión de Documentos (NUEVO)
- Registro de documentos de identidad (NIE, DNI, Pasaporte, etc.)
- Alertas automáticas de vencimiento
- Documentos con fotos (anverso/reverso)
- Estados automáticos (vigente/por vencer/vencido)
- Bloqueo de transferencias por documentos vencidos

### 💰 Transacciones
- Registro de transferencias por servicio
- Cálculo automático de comisiones
- Historial completo por cliente
- Estadísticas diarias/semanales/mensuales
- Verificación de límites

### 📊 Reportes y Estadísticas
- Dashboard interactivo
- Estadísticas en tiempo real
- Top clientes frecuentes
- Análisis de comisiones

### 📥📤 Importación/Exportación (NUEVO)
- **Exportar:** Clientes y transacciones a CSV/Excel
- **Importar:** Clientes masivos desde CSV
- **PDF:** Reportes individuales de clientes
- Validación automática y detección de duplicados

### 🔐 Seguridad
- Autenticación de usuarios
- Roles (Admin/Usuario)
- Variables de entorno para credenciales
- Registro de actividad (logs)

---

## 📋 Requisitos

- Python 3.8+
- Flask 2.3+
- SQLite (desarrollo) o MySQL (producción)

---

## 🛠️ Instalación Local

### 1. Clonar el repositorio
```bash
git clone <tu-repositorio>
cd Sistema_Control_Transferencias
```

### 2. Crear entorno virtual
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
# Copiar plantilla
cp .env.example .env

# Editar .env con tus configuraciones
# En Windows: notepad .env
# En Linux/Mac: nano .env
```

Generar SECRET_KEY segura:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Inicializar base de datos
```bash
# Crear estructura y datos de prueba
python init_db.py

# O crear migraciones para producción
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 6. Ejecutar aplicación
```bash
python run.py
```

Accede a: `http://localhost:5000`

**Credenciales de prueba:**
- Usuario: `admin` / Contraseña: `admin123`
- Usuario: `usuario` / Contraseña: `usuario123`

---

## 📦 Deployment a PythonAnywhere

**Ver guía completa en:** `DEPLOYMENT.md`

**Resumen rápido:**
1. Hacer backup de BD actual
2. Subir código a PythonAnywhere
3. Instalar dependencias
4. Ejecutar migraciones
5. Configurar WSGI
6. Reload aplicación

**⚠️ IMPORTANTE:** Tus datos existentes están seguros. Las migraciones solo agregan tablas nuevas.

---

## 📚 Uso del Sistema

### Gestión de Documentos

#### Agregar Documento a Cliente
1. Ir a **Clientes** → Seleccionar cliente
2. Click en **Documentos** en el perfil del cliente
3. **Agregar Documento**
4. Llenar formulario (tipo, número, vencimiento, fotos)
5. Marcar como "Documento Principal" si corresponde
6. **Guardar**

#### Ver Alertas de Vencimiento
1. **Dashboard** → Ver tarjeta "Docs. Vencidos"
2. O ir a **Documentos** → **Alertas**
3. Filtrar por "Vencidos" o "Por Vencer"

#### Renovar Documento Vencido
1. **Documentos** → Buscar documento vencido
2. Click **Editar**
3. Actualizar fecha de vencimiento
4. Subir nueva foto si es necesario
5. **Guardar**

---

### Importación/Exportación

#### Exportar Clientes a Excel
1. **Menú** → **Datos**
2. Sección "Exportar Datos"
3. Click **Exportar Clientes a Excel**
4. Se descarga automáticamente

#### Importar Clientes desde CSV
1. **Menú** → **Datos**
2. Click **Importar Clientes desde CSV**
3. Opción 1: Descargar plantilla de ejemplo
4. Preparar CSV con formato correcto:
   ```
   Nombre,Apellido,Documento,Teléfono,Fecha Nacimiento
   Juan,Pérez,X1234567A,612345678,1985-05-15
   ```
5. Subir archivo
6. Revisar validación (errores/duplicados)
7. **Confirmar** importación

#### Generar Reporte PDF de Cliente
1. Ir a perfil del cliente
2. Click **Exportar PDF** (o icono PDF)
3. Se descarga reporte con historial

---

## 🗂️ Estructura del Proyecto

```
Sistema_Control_Transferencias/
├── app/
│   ├── __init__.py                 # Factory de la app
│   ├── extensions.py               # Extensiones Flask
│   ├── models/                     # Modelos de datos
│   │   ├── cliente.py              # Cliente, Servicio
│   │   ├── transaccion.py          # Transacción, Notificación
│   │   ├── user.py                 # Usuario, ActivityLog
│   │   └── documento.py            # DocumentoCliente (NUEVO)
│   ├── routes/                     # Blueprints/Rutas
│   │   ├── auth.py                 # Autenticación
│   │   ├── main.py                 # Dashboard
│   │   ├── clientes.py             # CRUD Clientes
│   │   ├── transacciones.py        # CRUD Transacciones
│   │   ├── servicios.py            # CRUD Servicios
│   │   ├── calculadora.py          # Calculadora comisiones
│   │   ├── documentos.py           # CRUD Documentos (NUEVO)
│   │   └── data_management.py      # Import/Export (NUEVO)
│   ├── utils/                      # Utilidades (NUEVO)
│   │   ├── export_utils.py         # Exportación
│   │   └── import_utils.py         # Importación
│   ├── templates/                  # Plantillas HTML
│   └── static/                     # CSS, JS, imágenes
├── db/                             # Base de datos SQLite
├── migrations/                     # Migraciones Alembic
├── .env.example                    # Plantilla variables entorno
├── config.py                       # Configuración
├── init_db.py                      # Script inicialización
├── run.py                          # Punto de entrada
├── requirements.txt                # Dependencias
├── DEPLOYMENT.md                   # Guía deployment
└── RESUMEN_MEJORAS.md              # Resumen mejoras
```

---

## 🔧 Configuración

### Variables de Entorno (.env)

```bash
# Seguridad
SECRET_KEY=tu-clave-secreta-aqui

# Base de datos
DATABASE_URL=sqlite:///db/sistema_transferencias.db

# Uploads
UPLOAD_FOLDER=app/static/uploads
MAX_CONTENT_LENGTH=16777216  # 16MB

# Límites
LIMITE_TRANSFERENCIA_SEMANAL=999
DIAS_REESTABLECIMIENTO=7
DIAS_ALERTA_VENCIMIENTO=30
```

### Servicios de Transferencia

Configurar en: **Menú** → **Servicios** (solo admin)

Servicios de ejemplo:
- Western Union (3.5%)
- Mondial (2.8%)
- Monty (2.0%)
- Moneygram (3.2%)
- Ria (2.5%)

---

## 🗄️ Base de Datos

### Tablas Principales

1. **users** - Usuarios del sistema
2. **clientes** - Clientes registrados
3. **servicios** - Servicios de transferencia
4. **transacciones** - Transferencias realizadas
5. **documentos_cliente** - Documentos de identidad (NUEVO)
6. **notificaciones** - Notificaciones sistema
7. **activity_logs** - Logs de actividad

### Migraciones

```bash
# Crear nueva migración
flask db migrate -m "Descripción del cambio"

# Aplicar migraciones
flask db upgrade

# Revertir última migración
flask db downgrade
```

---

## 📊 API/Endpoints Principales

### Documentos
- `GET /documentos/` - Listar todos los documentos
- `GET /documentos/cliente/<id>` - Documentos de un cliente
- `GET /documentos/nuevo/<cliente_id>` - Formulario nuevo documento
- `POST /documentos/nuevo/<cliente_id>` - Crear documento
- `GET /documentos/editar/<id>` - Formulario editar
- `POST /documentos/editar/<id>` - Actualizar documento
- `POST /documentos/eliminar/<id>` - Eliminar documento
- `GET /documentos/alertas` - Ver alertas

### Datos (Import/Export)
- `GET /datos/` - Panel gestión de datos
- `GET /datos/exportar/clientes/csv` - Exportar clientes CSV
- `GET /datos/exportar/clientes/excel` - Exportar clientes Excel
- `GET /datos/exportar/transacciones/csv` - Exportar transacciones CSV
- `GET /datos/exportar/cliente/<id>/pdf` - Reporte PDF cliente
- `GET/POST /datos/importar` - Importar clientes
- `GET /datos/plantilla/clientes` - Descargar plantilla CSV

---

## 🛡️ Seguridad

### Buenas Prácticas Implementadas

✅ Variables de entorno para credenciales  
✅ Hash de contraseñas (Werkzeug)  
✅ Sesiones seguras (Flask-Login)  
✅ Protección CSRF en formularios  
✅ Validación de archivos subidos  
✅ Límite de tamaño de archivos (16MB)  
✅ Registro de actividad de usuarios  

### Recomendaciones Adicionales

- Cambiar credenciales por defecto
- Usar HTTPS en producción
- Hacer backups regulares de la BD
- Revisar logs de actividad
- Actualizar dependencias regularmente

---

## 🐛 Solución de Problemas

### Error: ModuleNotFoundError
```bash
# Asegúrate de estar en el entorno virtual
pip install -r requirements.txt
```

### Error: No such table
```bash
# Ejecutar migraciones
python init_db.py
# o
flask db upgrade
```

### Excel no funciona
Si `pandas` no se puede instalar, las exportaciones Excel volverán automáticamente a CSV.

### PDF no funciona
Si `reportlab` no está disponible, la opción no aparecerá. Usa exportación CSV/Excel.

---

## 📞 Soporte

Para problemas de deployment a PythonAnywhere, consulta `DEPLOYMENT.md`.

Para resumen de mejoras implementadas, consulta `RESUMEN_MEJORAS.md`.

---

## 📝 Changelog

### Versión 2.0 (Enero 2026)
- ✨ Gestión completa de documentos de identidad
- ✨ Sistema de alertas de vencimiento
- ✨ Importación masiva de clientes (CSV)
- ✨ Exportación de datos (CSV, Excel, PDF)
- 🔒 Seguridad mejorada (variables de entorno)
- 📊 Dashboard con estadísticas de documentos
- 🎨 Navegación mejorada

### Versión 1.0
- Gestión de clientes y transacciones
- Control de límites semanales
- Autenticación y roles
- Calculadora de comisiones
- Dashboard básico

---

## 📄 Licencia

Proyecto privado de gestión interna.

---

## 👨‍💻 Desarrollo

Desarrollado con:
- Flask 2.3
- SQLAlchemy 3.1
- Bootstrap 5
- Font Awesome 6
- Pandas (export)
- ReportLab (PDF)
