// URL por defecto del sistema. Cada negocio puede cambiarla desde el popup
// (queda guardada en chrome.storage.sync y se sincroniza entre sus navegadores).
const DEFAULT_BASE_URL = 'https://sistemacontroltransferenciasrailway-production.up.railway.app';
let BASE_URL = DEFAULT_BASE_URL;

// Helpers para timeouts
function withTimeout(promise, ms, reason) {
  return Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error(reason || 'Timeout')), ms)
    )
  ]);
}

// Normaliza la URL ingresada: sin espacios, sin barra final, con protocolo
function normalizarBaseUrl(url) {
  let u = (url || '').trim().replace(/\/+$/, '');
  if (u && !/^https?:\/\//i.test(u)) u = 'https://' + u;
  return u;
}

document.addEventListener('DOMContentLoaded', async () => {
  const btnAuto = document.getElementById('btnEnviar');
  const btnManual = document.getElementById('btnEnviarManual');
  const btnToggle = document.getElementById('btnToggleManual');
  const manualBox = document.getElementById('manualBox');
  const manualText = document.getElementById('manualText');
  const status = document.getElementById('status');
  const siteLabel = document.getElementById('site');
  const btnToggleConfig = document.getElementById('btnToggleConfig');
  const configBox = document.getElementById('configBox');
  const configUrl = document.getElementById('configUrl');
  const btnGuardarConfig = document.getElementById('btnGuardarConfig');
  const configMsg = document.getElementById('configMsg');

  // Cargar la URL guardada (si existe)
  try {
    const stored = await chrome.storage.sync.get('baseUrl');
    if (stored.baseUrl) BASE_URL = stored.baseUrl;
  } catch {
    // Si falla el storage, se usa la URL por defecto
  }
  configUrl.value = BASE_URL;

  // Toggle caja de configuración
  btnToggleConfig.addEventListener('click', () => {
    configBox.classList.toggle('visible');
    if (configBox.classList.contains('visible')) {
      configUrl.focus();
    }
  });

  // Guardar URL del negocio
  btnGuardarConfig.addEventListener('click', async () => {
    const url = normalizarBaseUrl(configUrl.value);
    if (!url) {
      configMsg.textContent = '❌ Ingresá una URL válida.';
      configMsg.className = 'config-msg error';
      return;
    }
    btnGuardarConfig.disabled = true;
    configMsg.textContent = 'Verificando...';
    configMsg.className = 'config-msg';

    // Verificar que el sistema responda (no bloquea el guardado si falla)
    let alcanzable = false;
    try {
      const resp = await withTimeout(fetch(url, { method: 'GET', redirect: 'follow' }), 8000, 'Timeout');
      alcanzable = resp.ok || resp.status === 401 || resp.status === 403;
    } catch {
      alcanzable = false;
    }

    try {
      await chrome.storage.sync.set({ baseUrl: url });
      BASE_URL = url;
      configMsg.textContent = alcanzable
        ? '✅ URL guardada y verificada.'
        : '⚠️ URL guardada, pero el sistema no respondió. Revisá que esté en línea.';
      configMsg.className = 'config-msg ' + (alcanzable ? 'success' : 'error');
    } catch {
      configMsg.textContent = '❌ No se pudo guardar la URL.';
      configMsg.className = 'config-msg error';
    }
    btnGuardarConfig.disabled = false;
  });

  // Detectar sitio actual
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url) {
      const host = new URL(tab.url).hostname;
      siteLabel.textContent = host;
    } else {
      siteLabel.textContent = 'ventana emergente / app';
    }
  } catch {
    siteLabel.textContent = 'desconocido';
  }

  // Toggle modo manual
  btnToggle.addEventListener('click', () => {
    manualBox.classList.toggle('visible');
    if (manualBox.classList.contains('visible')) {
      manualText.focus();
    }
  });

  // Envío automático (desde la pestaña activa)
  btnAuto.addEventListener('click', async () => {
    await enviarRecibo({ modo: 'auto', btn: btnAuto, status });
  });

  // Envío manual (desde textarea)
  btnManual.addEventListener('click', async () => {
    const texto = manualText.value.trim();
    if (!texto) {
      status.textContent = '❌ El campo está vacío. Pegá el texto del recibo.';
      status.className = 'error';
      return;
    }
    await enviarRecibo({ modo: 'manual', texto, btn: btnManual, status });
  });
});

async function enviarRecibo({ modo, texto: textoManual, btn, status }) {
  btn.disabled = true;
  status.textContent = modo === 'auto' ? 'Leyendo recibo...' : 'Analizando...';
  status.className = '';

  try {
    let texto = textoManual || '';

    if (modo === 'auto') {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab) throw new Error('No se encontró la pestaña activa');

      const url = tab.url || '';

      // Detectar URLs donde no se puede inyectar scripts
      if (url.startsWith('about:') || url.startsWith('chrome://') || url.startsWith('chrome-extension://') || url.startsWith('edge://')) {
        throw new Error('No se puede leer esta pestaña. Probá seleccionando el texto del recibo, copiándolo y usando "Pegar recibo manualmente".');
      }

      let textoContent = '';
      let textoInyectado = '';

      // Intento 1: preguntar al content script (mejor para popups/iframes)
      try {
        const resp = await withTimeout(
          new Promise((resolve, reject) => {
            chrome.tabs.sendMessage(tab.id, { action: 'extraerRecibo' }, (response) => {
              if (chrome.runtime.lastError) {
                reject(new Error(chrome.runtime.lastError.message));
              } else {
                resolve(response);
              }
            });
          }),
          4000,
          'El content script no respondió'
        );
        if (resp && resp.texto) textoContent = resp.texto;
      } catch (e) {
        // Content script no disponible o no respondió
      }

      // Intento 2: inyección directa
      if (!textoContent) {
        try {
          const results = await withTimeout(
            chrome.scripting.executeScript({
              target: { tabId: tab.id },
              func: () => {
                const seleccion = window.getSelection ? window.getSelection().toString().trim() : '';
                if (seleccion && seleccion.length > 20) return seleccion;

                const posibles = document.querySelectorAll(
                  '[class*="receipt" i], [class*="recibo" i], [class*="ticket" i], ' +
                  '[id*="receipt" i], [id*="recibo" i], ' +
                  'table, .container, .content, main, article, [role="dialog"]'
                );
                let mejor = document.body;
                for (const el of posibles) {
                  const t = el.innerText || '';
                  if (/Mittente|Importo|Totale|MTCN|Reference|Amount|Sender|Ordinante|Beneficiario/i.test(t)) {
                    if (t.length < 8000) { mejor = el; break; }
                  }
                }
                return mejor.innerText || '';
              }
            }),
            5000,
            'La pestaña no respondió a tiempo'
          );
          textoInyectado = results[0]?.result || '';
        } catch (e) {
          // Falló inyección
        }
      }

      texto = textoContent || textoInyectado;
      if (!texto.trim()) {
        throw new Error('No se pudo leer texto del recibo. Probá seleccionando el texto en la página, copiándolo y usando "Pegar recibo manualmente".');
      }
    }

    status.textContent = 'Analizando...';

    const resp = await fetch(BASE_URL + '/transacciones/api/analizar-recibo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto })
    });

    if (!resp.ok) {
      if (resp.status === 404) throw new Error('Error 404: La URL del servidor no existe. Verificá que el sistema esté en línea.');
      if (resp.status === 401 || resp.status === 403) throw new Error('Error ' + resp.status + ': No estás logueado en el sistema. Abrí el sistema en otra pestaña e iniciá sesión.');
      throw new Error('Error del servidor: ' + resp.status);
    }

    const datos = await resp.json();

    // Construir URL con query params
    const params = new URLSearchParams();
    if (datos.documento) params.set('doc', datos.documento);
    if (datos.nombre) params.set('nom', datos.nombre);
    if (datos.apellido) params.set('ape', datos.apellido);
    if (datos.telefono) params.set('tel', datos.telefono);
    if (datos.monto) params.set('mon', String(datos.monto).replace('.', ','));
    if (datos.servicio_hint) params.set('srv', datos.servicio_hint);

    const url = BASE_URL + '/transacciones/registro-rapido?' + params.toString();

    status.textContent = '✅ Abriendo sistema...';
    status.className = 'success';

    await chrome.tabs.create({ url });
    window.close();

  } catch (err) {
    status.textContent = '❌ ' + err.message;
    status.className = 'error';
    btn.disabled = false;
  }
}
