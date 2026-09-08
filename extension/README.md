# Extensión Chrome — Registro Rápido (v1.2)

Captura de recibos y consulta de saldos en 1 clic para Western Union, MoneyGram, Ria, Mondial Bony y Monty.

---

## 🚀 Novedades v1.2

1. **⚡ Botón Flotante en Pantalla**: Cuando terminás una transferencia en el portal de la remesadora, aparece automáticamente un botón flotante `[ ⚡ Registrar en Sistema ]` en la esquina inferior. Un solo clic y se abre el Registro Rápido.
2. **⌨️ Atajo de Teclado `Alt + R`**: Presioná `Alt + R` en cualquier momento para capturar el recibo de la pantalla actual sin tocar el ratón.
3. **🔍 Consulta de Saldo y Límite Semanal**: En la pestaña **"Consultar Saldo"** del popup, buscá cualquier cliente por nombre o documento y mirá al instante:
   - Su saldo disponible en la ventana móvil de 7 días (ej: `750,00 € / 999 €`).
   - Estado y vigencia de sus documentos (vigente / por vencer / vencido).
   - Documentos adicionales vinculados.
   - Botón directo para iniciar transferencia.
4. **🔢 Auto-captura de MTCN y Referencia**: Extrae automáticamente el MTCN (Western Union), PIN (Ria) o código de referencia y lo pre-llena en el sistema y mensajes de WhatsApp.
5. **🏷️ Insignia ⚡ de Detección**: El ícono de la extensión muestra una insignia naranja `⚡` cuando detecta un recibo en la pestaña activa.

---

## 💻 Instalación

1. Abrí Google Chrome y andá a `chrome://extensions/`
2. Activá el interruptor **"Modo de desarrollador"** (arriba a la derecha).
3. Hacé clic en **"Cargar sin comprimir"** (o "Cargar descomprimida").
4. Seleccioná la carpeta `extension/` de este proyecto.
5. *(Opcional)* Fijá la extensión en la barra de herramientas haciendo clic en el ícono de la pieza de puzzle 🧩 y luego en la chincheta 📌.

---

## ⚙️ Configuración de URL

Cada negocio tiene su propio acceso o URL. Para configurarla:

1. Hacé clic en el ícono ⚡ de la extensión.
2. Clic en **"⚙️ Configurar URL del sistema"**.
3. Ingresá la URL de tu negocio (ej: `https://sistemacontroltransferenciasrailway-production.up.railway.app`).
4. Hacé clic en **"💾 Guardar URL"**.

*Se sincroniza automáticamente en todos tus navegadores de Chrome donde uses la misma cuenta de Google.*

---

## 📖 Formas de Uso

### 1. Con el Botón Flotante (Más Rápido)
Al estar en la página de confirmación de WU, Ria, MoneyGram o Mondial, aparecerá el botón `[ ⚡ Registrar en Sistema ]`. Hacé clic sobre él y listo.

### 2. Con el Atajo de Teclado
Presioná **`Alt + R`** mientras ves el recibo en pantalla.

### 3. Desde el Ícono de la Extensión
Hacé clic en el ícono ⚡ y presioná **"📋 Enviar recibo automático"**.

### 4. Modo Manual (Ventanas emergentes bloqueadas o Monty)
Si estás en una ventana emergente o app externa:
1. Copiá el texto del recibo (`Ctrl + C`).
2. Abrí la extensión y hacé clic en **"✏️ Pegar recibo manualmente"**.
3. Pegá el texto (`Ctrl + V`) y presioná **"Procesar texto"**.

### 5. Consultar Límite y Estado del Cliente
1. Abrí la extensión y cambiá a la pestaña **"🔍 Consultar Saldo"**.
2. Escribí el nombre o número de documento del cliente.
3. Verás en tiempo real si puede enviar, cuánto dinero le queda disponible esta semana y el estado de su documentación.

---

## 🔒 Requisitos

- Debés tener la sesión iniciada en el sistema (abrir tu sistema en una pestaña de Chrome e iniciar sesión), ya que la extensión consulta de forma segura usando tu sesión.
