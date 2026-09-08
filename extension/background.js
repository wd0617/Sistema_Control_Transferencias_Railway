// Background service worker para la extensión de Registro Rápido
const DEFAULT_BASE_URL = 'https://sistemacontroltransferenciasrailway-production.up.railway.app';

async function getBaseUrl() {
  try {
    const stored = await chrome.storage.sync.get('baseUrl');
    return stored.baseUrl || DEFAULT_BASE_URL;
  } catch {
    return DEFAULT_BASE_URL;
  }
}

async function procesarTextoRecibo(texto) {
  if (!texto || !texto.trim()) {
    throw new Error('No se detectó texto de recibo.');
  }

  const baseUrl = await getBaseUrl();
  const resp = await fetch(baseUrl + '/transacciones/api/analizar-recibo', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texto })
  });

  if (!resp.ok) {
    if (resp.status === 401 || resp.status === 403) {
      throw new Error('Sesión no iniciada en el sistema. Abrí el sistema e iniciá sesión.');
    }
    throw new Error(`Error en el servidor (${resp.status})`);
  }

  const datos = await resp.json();

  const params = new URLSearchParams();
  if (datos.documento) params.set('doc', datos.documento);
  if (datos.nombre) params.set('nom', datos.nombre);
  if (datos.apellido) params.set('ape', datos.apellido);
  if (datos.telefono) params.set('tel', datos.telefono);
  if (datos.monto) params.set('mon', String(datos.monto).replace('.', ','));
  if (datos.servicio_hint) params.set('srv', datos.servicio_hint);
  if (datos.referencia) params.set('ref', datos.referencia);

  const url = baseUrl + '/transacciones/registro-rapido?' + params.toString();
  await chrome.tabs.create({ url });
  return { ok: true, url, datos };
}

// Escucha atajos de teclado (Alt + R)
chrome.commands.onCommand.addListener(async (command) => {
  if (command === 'capturar_recibo') {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) return;

    try {
      // Intentar extraer texto con el content script
      chrome.tabs.sendMessage(tab.id, { action: 'extraerRecibo' }, async (response) => {
        let texto = response?.texto;
        if (!texto) {
          // Fallback con scripting
          try {
            const results = await chrome.scripting.executeScript({
              target: { tabId: tab.id },
              func: () => {
                const s = window.getSelection ? window.getSelection().toString().trim() : '';
                return s || document.body.innerText || '';
              }
            });
            texto = results[0]?.result || '';
          } catch (e) {
            console.error('Error inyectando script:', e);
          }
        }

        if (texto) {
          await procesarTextoRecibo(texto);
        }
      });
    } catch (err) {
      console.error('Error procesando comando capturar_recibo:', err);
    }
  }
});

// Escucha mensajes de content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'reciboDetectado' && sender.tab && sender.tab.id) {
    chrome.action.setBadgeText({ tabId: sender.tab.id, text: '⚡' });
    chrome.action.setBadgeBackgroundColor({ tabId: sender.tab.id, color: '#ff8c00' });
    sendResponse({ ok: true });
    return false;
  }

  if (request.action === 'procesarRecibo') {
    procesarTextoRecibo(request.texto)
      .then((res) => sendResponse(res))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true; // Asíncrono
  }

  return false;
});
