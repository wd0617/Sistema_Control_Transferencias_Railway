// URL del sistema en Railway
const API_URL = 'https://sistemacontroltransferenciasrailway-production.up.railway.app/api/analizar-recibo';
const APP_URL = 'https://sistemacontroltransferenciasrailway-production.up.railway.app/transacciones/registro-rapido';

document.addEventListener('DOMContentLoaded', async () => {
  const btn = document.getElementById('btnEnviar');
  const status = document.getElementById('status');
  const siteLabel = document.getElementById('site');

  // Detectar sitio actual
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) {
    const host = new URL(tab.url).hostname;
    siteLabel.textContent = host;
  }

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    status.textContent = 'Leyendo recibo...';
    status.className = '';

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab) throw new Error('No se encontró la pestaña activa');

      // Ejecutar script en la pestaña para extraer texto visible
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          // Intentar encontrar el recibo en el DOM
          // Estrategia: buscar contenedores que parezcan recibos
          const posibles = document.querySelectorAll(
            '[class*="receipt"], [class*="recibo"], [class*="ticket"], ' +
            '[id*="receipt"], [id*="recibo"], ' +
            'table, .container, .content, main, article'
          );
          let mejor = document.body;
          for (const el of posibles) {
            const texto = el.innerText || '';
            // El recibo suele tener keywords como Mittente, Importo, Totale
            if (/Mittente|Importo|Totale|MTCN|Reference|Amount|Sender/i.test(texto)) {
              if (texto.length < 5000) mejor = el; // preferir el más pequeño que tenga keywords
            }
          }
          return mejor.innerText || '';
        }
      });

      const texto = results[0]?.result || '';
      if (!texto.trim()) {
        throw new Error('No se pudo leer texto del recibo. Probá seleccionando el texto manualmente y copiándolo.');
      }

      status.textContent = 'Analizando...';

      const resp = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texto: texto })
      });

      if (!resp.ok) throw new Error('Error del servidor: ' + resp.status);

      const datos = await resp.json();

      // Construir URL con query params
      const params = new URLSearchParams();
      if (datos.documento) params.set('doc', datos.documento);
      if (datos.nombre) params.set('nom', datos.nombre);
      if (datos.apellido) params.set('ape', datos.apellido);
      if (datos.telefono) params.set('tel', datos.telefono);
      if (datos.monto) params.set('mon', String(datos.monto).replace('.', ','));
      if (datos.servicio_hint) params.set('srv', datos.servicio_hint);

      const url = APP_URL + '?' + params.toString();

      status.textContent = '✅ Abriendo sistema...';
      status.className = 'success';

      await chrome.tabs.create({ url });
      window.close();

    } catch (err) {
      status.textContent = '❌ ' + err.message;
      status.className = 'error';
      btn.disabled = false;
    }
  });
});
