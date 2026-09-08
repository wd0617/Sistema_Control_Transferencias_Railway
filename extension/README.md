# Extensión Chrome — Registro Rápido

## Instalación

1. Abrí Chrome y andá a `chrome://extensions/`
2. Activá **"Modo desarrollador"** (arriba a la derecha)
3. Hacé clic en **"Cargar sin comprimir"**
4. Seleccioná esta carpeta `extension/`

## Configuración

Cada negocio tiene su propia instancia del sistema (su propia URL). Para apuntar la extensión a la tuya:

1. Hacé clic en el ícono ⚡ de la extensión
2. Apretá **"⚙️ Configurar URL del sistema"**
3. Ingresá la URL de tu negocio (ej: `https://tu-negocio.up.railway.app`)
4. Apretá **"💾 Guardar URL"**

La extensión verifica que el sistema responda y guarda la URL con `chrome.storage.sync` (se sincroniza entre tus navegadores con la misma cuenta de Google). Si no configurás nada, usa la URL por defecto que viene en `popup.js` (`DEFAULT_BASE_URL`).

## Uso

### Modo automático (recomendado)
1. Terminá una transacción en Western Union, MoneyGram, Ria o Mondial Bony
2. Hacé clic en el ícono ⚡ de la extensión
3. Apretá **"Enviar recibo automático"**
4. Se abre automáticamente el Registro Rápido con los datos pre-llenos

### ¿Ventana emergente / popup?
Si el recibo se abre en una ventana emergente:
1. Seleccioná todo el texto del recibo (`Ctrl+A` o `Cmd+A`)
2. Abrí la extensión y apretá **"Enviar recibo automático"**
3. Si no detecta nada, usá el modo manual

### Modo manual (Monty, popups, apps)
1. Copiá el texto del recibo (de la app de Monty, de un PDF, etc.)
2. Abrí la extensión
3. Apretá **"Pegar recibo manualmente"**
4. Pegá el texto en el campo
5. Apretá **"Enviar texto manual"**

## Requisitos

- Tenés que estar logueado en el sistema (abrirlo en otra pestaña) porque la API requiere sesión.
