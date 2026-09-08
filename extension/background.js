// Background service worker para la extensión de Registro Rápido
const DEFAULT_BASE_URL = 'https://sistemacontroltransferenciasrailway-production.up.railway.app';

let ultimoReciboBuffer = null;

// Cargar último recibo desde storage al iniciar
chrome.storage.local.get(['ultimoReciboBuffer'], (res) => {
  if (res && res.ultimoReciboBuffer) {
    ultimoReciboBuffer = res.ultimoReciboBuffer;
  }
});

async function getConfig() {
  try {
    const stored = await chrome.storage.sync.get(['baseUrl', 'negocioId']);
    return {
      baseUrl: stored.baseUrl || DEFAULT_BASE_URL,
      negocioId: stored.negocioId || ''
    };
  } catch {
    return { baseUrl: DEFAULT_BASE_URL, negocioId: '' };
  }
}

async function procesarTextoRecibo(texto) {
  if (!texto || !texto.trim()) {
    throw new Error('No se detectó texto de recibo.');
  }

  const { baseUrl, negocioId } = await getConfig();
  const headers = { 'Content-Type': 'application/json' };
  if (negocioId) headers['X-Negocio-Id'] = negocioId;

  const apiUrl = `${baseUrl}/transacciones/api/analizar-recibo${negocioId ? `?negocio_id=${encodeURIComponent(negocioId)}` : ''}`;
  const resp = await fetch(apiUrl, {
    method: 'POST',
    headers,
    credentials: 'include',
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
  if (negocioId) params.set('negocio_id', negocioId);

  const url = baseUrl + '/transacciones/registro-rapido?' + params.toString();
  await chrome.tabs.create({ url });

  // Limpiar badge tras procesar
  chrome.action.setBadgeText({ text: '' });
  return { ok: true, url, datos };
}

// Extrae texto de una pestaña con fallback de scripting
async function extraerTextoDeTab(tabId) {
  try {
    const resp = await new Promise((resolve) => {
      chrome.tabs.sendMessage(tabId, { action: 'extraerRecibo' }, (r) => {
        if (chrome.runtime.lastError) resolve(null);
        else resolve(r);
      });
    });
    if (resp && resp.texto && resp.texto.length > 30) return resp.texto;
  } catch {}

  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const s = window.getSelection ? window.getSelection().toString().trim() : '';
        if (s && s.length > 20) return s;
        const modal = document.querySelector('.modal.show, [role="dialog"]:not([aria-hidden="true"]), .receipt-dialog, .swal2-modal, [class*="modal" i][style*="block"], print-preview-app, #print-area, .print-section');
        if (modal && modal.innerText && modal.innerText.length > 50) return modal.innerText.trim();
        return (document.body ? document.body.innerText : '') || '';
      }
    });
    const txt = results[0]?.result || '';
    if (txt && txt.length > 30) return txt;
  } catch {}

  return null;
}

// Escucha atajos de teclado (Alt + R)
chrome.commands.onCommand.addListener(async (command) => {
  if (command === 'capturar_recibo') {
    let textoFinal = null;

    // 1. Intentar con la pestaña activa
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.id) {
      const txt = await extraerTextoDeTab(tab.id);
      if (txt && /mittente|importo|totale|mtcn|pin|riferimento|sender|amount|mondial|western union|ria|moneygram/i.test(txt)) {
        textoFinal = txt;
      }
    }

    // 2. Si la pestaña activa no tiene recibo o está congelada, usar el buffer reciente
    if (!textoFinal && ultimoReciboBuffer && (Date.now() - (ultimoReciboBuffer.timestamp || 0)) < 300000) {
      textoFinal = ultimoReciboBuffer.texto;
    }

    // 3. Si aún no hay texto, escanear otras pestañas/ventanas abiertas (popups de impresión, WUPOS, etc.)
    if (!textoFinal) {
      try {
        const tabs = await chrome.tabs.query({});
        for (const t of tabs) {
          if (!t.id || (tab && t.id === tab.id)) continue;
          const urlOtitulo = ((t.url || '') + ' ' + (t.title || '')).toLowerCase();
          const esCandidata = /print|receipt|recibo|wupos|western|mondial|ria|moneygram|pos/.test(urlOtitulo);
          if (esCandidata) {
            const txt = await extraerTextoDeTab(t.id);
            if (txt && /mittente|importo|totale|mtcn|pin|riferimento|sender|amount|mondial|western union|ria|moneygram/i.test(txt)) {
              textoFinal = txt;
              break;
            }
          }
        }
      } catch (e) {
        console.error('Error escaneando tabs:', e);
      }
    }

    if (textoFinal) {
      try {
        await procesarTextoRecibo(textoFinal);
      } catch (err) {
        console.error('Error al procesar recibo con Alt+R:', err);
      }
    }
  }
});

// Escucha mensajes de content scripts y popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Cuando un content script detecta un recibo (o beforeprint), lo guardamos en buffer
  if (request.action === 'guardarReciboBuffer') {
    ultimoReciboBuffer = {
      texto: request.texto,
      url: request.url,
      titulo: request.titulo,
      timestamp: Date.now(),
      tabId: sender.tab ? sender.tab.id : null
    };
    chrome.storage.local.set({ ultimoReciboBuffer });
    chrome.action.setBadgeText({ text: '⚡' });
    chrome.action.setBadgeBackgroundColor({ color: '#ff8c00' });
    sendResponse({ ok: true });
    return false;
  }

  // Devolver el buffer al popup
  if (request.action === 'obtenerReciboBuffer') {
    const esValido = ultimoReciboBuffer && (Date.now() - (ultimoReciboBuffer.timestamp || 0)) < 300000;
    sendResponse({ buffer: esValido ? ultimoReciboBuffer : null });
    return false;
  }

  // Limpiar buffer
  if (request.action === 'limpiarReciboBuffer') {
    ultimoReciboBuffer = null;
    chrome.storage.local.remove(['ultimoReciboBuffer']);
    chrome.action.setBadgeText({ text: '' });
    sendResponse({ ok: true });
    return false;
  }

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
