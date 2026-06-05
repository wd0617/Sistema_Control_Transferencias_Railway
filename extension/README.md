# Extensión Chrome — Registro Rápido

## Instalación

1. Abrí Chrome y andá a `chrome://extensions/`
2. Activá **"Modo desarrollador"** (arriba a la derecha)
3. Hacé clic en **"Cargar sin comprimir"**
4. Seleccioná esta carpeta `extension/`

## Configuración

1. Abrí `popup.js`
2. Cambiá estas dos líneas por la URL de tu app en Railway:

```js
const API_URL = 'https://TUDOMINIO.railway.app/api/analizar-recibo';
const APP_URL = 'https://TUDOMINIO.railway.app/transacciones/registro-rapido';
```

3. Guardá el archivo
4. En `chrome://extensions/`, hacé clic en el ícono de recargar (🔄) en la tarjeta de la extensión

## Uso

1. Terminá una transacción en Western Union, MoneyGram, Ria, Mondial Bony o Monty
2. Hacé clic en el ícono ⚡ de la extensión
3. Apretá **"Enviar recibo al sistema"**
4. Se abre automáticamente el Registro Rápido con los datos pre-llenos
5. Corregí si hace falta y guardá
