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
  // Pestañas
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add('active');
    });
  });

  // Elementos Tab Recibo
  const btnAuto = document.getElementById('btnEnviar');
  const btnManual = document.getElementById('btnEnviarManual');
  const btnToggle = document.getElementById('btnToggleManual');
  const manualBox = document.getElementById('manualBox');
  const manualText = document.getElementById('manualText');
  const status = document.getElementById('status');
  const siteLabel = document.getElementById('site');

  // Elementos Tab Cliente
  const inputBuscar = document.getElementById('inputBuscarCliente');
  const listaClientes = document.getElementById('listaClientes');
  const statusCliente = document.getElementById('statusCliente');

  // Elementos Config
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

  // Envío automático
  btnAuto.addEventListener('click', async () => {
    await enviarRecibo({ modo: 'auto', btn: btnAuto, status });
  });

  // Envío manual
  btnManual.addEventListener('click', async () => {
    const texto = manualText.value.trim();
    if (!texto) {
      status.textContent = '❌ El campo está vacío. Pegá el texto del recibo.';
      status.className = 'error';
      return;
    }
    await enviarRecibo({ modo: 'manual', texto, btn: btnManual, status });
  });

  // Búsqueda de cliente con debounce
  let searchTimer = null;
  inputBuscar.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const q = inputBuscar.value.trim();
    if (q.length < 2) {
      listaClientes.innerHTML = '<div style="text-align: center; color: var(--text-muted); font-size: 12px; padding: 20px 0;">Escribe al menos 2 caracteres...</div>';
      statusCliente.textContent = '';
      return;
    }
    statusCliente.textContent = 'Buscando...';
    searchTimer = setTimeout(() => buscarClientes(q, listaClientes, statusCliente), 350);
  });
});

// Buscar y renderizar clientes
async function buscarClientes(query, container, statusLabel) {
  try {
    const resp = await fetch(`${BASE_URL}/transacciones/api/verificar-cliente?q=${encodeURIComponent(query)}`);
    if (!resp.ok) {
      if (resp.status === 401 || resp.status === 403) {
        statusLabel.textContent = '⚠️ Iniciá sesión en el sistema para consultar.';
        container.innerHTML = '<div style="text-align:center; padding:15px; color:#b91c1c; font-size:12px;">Debes estar autenticado en el sistema.</div>';
        return;
      }
      throw new Error(`Error ${resp.status}`);
    }

    const data = await resp.json();
    const clientes = data.clientes || [];
    statusLabel.textContent = clientes.length ? `${clientes.length} resultado(s)` : 'Sin resultados';

    if (clientes.length === 0) {
      container.innerHTML = '<div style="text-align: center; color: var(--text-muted); font-size: 12px; padding: 20px 0;">No se encontró ningún cliente registrado.</div>';
      return;
    }

    let html = '';
    clientes.forEach(c => {
      const saldoOk = c.saldo_disponible > 0;
      const saldoCls = saldoOk ? 'badge-ok' : 'badge-limit';
      const docCls = `doc-${c.estado_documento || 'vigente'}`;
      const docLabel = (c.estado_documento || 'vigente').replace('_', ' ').toUpperCase();

      let docsExtrasHtml = '';
      if (c.documentos_adicionales && c.documentos_adicionales.length > 0) {
        docsExtrasHtml = `<div style="font-size: 10px; color: #4b5563; margin-top: 3px;">
          📎 Otros doc: ${c.documentos_adicionales.map(d => `${d.tipo} ${d.numero}`).join(', ')}
        </div>`;
      }

      // Parámetros para Registro Rápido
      const params = new URLSearchParams();
      params.set('doc', c.documento);
      params.set('nom', c.nombre);
      if (c.apellido) params.set('ape', c.apellido);
      if (c.telefono) params.set('tel', c.telefono);
      const urlRapido = `${BASE_URL}/transacciones/registro-rapido?${params.toString()}`;

      html += `
        <div class="client-card">
          <div class="client-header">
            <span class="client-name">${escapeHtml(c.nombre)} ${escapeHtml(c.apellido || '')}</span>
            <span class="balance-badge ${saldoCls}">
              ${c.saldo_disponible.toFixed(2)} € disp.
            </span>
          </div>
          <div class="client-sub">
            <span>🪪 ${escapeHtml(c.tipo_documento)}: <strong>${escapeHtml(c.documento)}</strong></span>
            <span class="badge-doc ${docCls}">${docLabel}</span>
          </div>
          ${docsExtrasHtml}
          ${!saldoOk ? `<div style="font-size:11px; color:#b91c1c; margin-top:2px;">⚠️ Límite de ${c.limite_semanal}€ alcanzado. Reestablece en ${c.dias_reestablecimiento} día(s).</div>` : ''}
          <a href="${urlRapido}" target="_blank" class="btn-send-fast">⚡ Iniciar Registro Rápido</a>
        </div>
      `;
    });

    container.innerHTML = html;

  } catch (err) {
    statusLabel.textContent = '❌ Error al consultar';
    container.innerHTML = `<div style="color:#b91c1c; font-size:11px; padding:10px;">${err.message}</div>`;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[m]);
}

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

      if (url.startsWith('about:') || url.startsWith('chrome://') || url.startsWith('chrome-extension://') || url.startsWith('edge://')) {
        throw new Error('No se puede leer esta pestaña del navegador. Probá seleccionando el texto del recibo y usando "Pegar recibo manualmente".');
      }

      let textoContent = '';
      let textoInyectado = '';

      // Intento 1: preguntar al content script
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
      } catch (e) {}

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
        } catch (e) {}
      }

      texto = textoContent || textoInyectado;
      if (!texto.trim()) {
        throw new Error('No se pudo leer texto del recibo. Probá seleccionando el texto en la página, copiándolo y usando "Pegar recibo manualmente".');
      }
    }

    status.textContent = 'Analizando en el sistema...';

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
    if (datos.referencia) params.set('ref', datos.referencia);

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
