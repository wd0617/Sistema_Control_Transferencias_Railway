# Extensión Chrome — Registro Rápido

## Instalación

1. Abrí Chrome y andá a `chrome://extensions/`
2. Activá **"Modo desarrollador"** (arriba a la derecha)
3. Hacé clic en **"Cargar sin comprimir"**
4. Seleccioná esta carpeta `extension/`

## Configuración

La extensión ya viene configurada con la URL de Railway. Si cambia, editá estas líneas en `popup.js`:

```js
const BASE_URL = 'https://sistemacontroltransferenciasrailway-production.up.railway.app';
```

Guardá el archivo y recargá la extensión en `chrome://extensions/`.

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
